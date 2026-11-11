"""Field-level protection for participant identifiers and transcripts.

Emails and message bodies are encrypted with AES-256-GCM before they touch
Postgres. A keyed HMAC index is stored alongside the email so conversations can
still be looked up by address without keeping the address in plaintext.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import logging
import os
from functools import lru_cache
from typing import Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_KEY_BYTES = 32
_NONCE_BYTES = 12
_CIPHER_PREFIX = "v1:"
_EMAIL_INDEX_CONTEXT = b"unmc-rag:email-index:"
_LEGACY_INDEX_CONTEXT = b"unmc-rag:email-index:plain:"

logger = logging.getLogger(__name__)


class FieldCipher(Protocol):
    enabled: bool

    def encrypt(self, value: str) -> str: ...

    def decrypt(self, value: str | None) -> str: ...

    def email_index(self, email: str) -> str: ...


class AesFieldCipher:
    """AES-256-GCM text encryption plus a deterministic email blind index."""

    enabled = True

    def __init__(self, key: bytes) -> None:
        if len(key) != _KEY_BYTES:
            raise ValueError("Encryption key must be 32 bytes")
        self._key = key
        self._aead = AESGCM(key)

    def encrypt(self, value: str) -> str:
        if not value:
            return ""
        nonce = os.urandom(_NONCE_BYTES)
        sealed = self._aead.encrypt(nonce, value.encode("utf-8"), None)
        return _CIPHER_PREFIX + base64.urlsafe_b64encode(nonce + sealed).decode("ascii")

    def decrypt(self, value: str | None) -> str:
        if not value:
            return ""
        if not value.startswith(_CIPHER_PREFIX):
            # Rows written before encryption was enabled stay readable.
            return value
        try:
            raw = base64.urlsafe_b64decode(value[len(_CIPHER_PREFIX) :])
            nonce, sealed = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
            return self._aead.decrypt(nonce, sealed, None).decode("utf-8")
        except (binascii.Error, ValueError, InvalidTag):
            logger.warning("Could not decrypt an encrypted field; returning empty value")
            return ""

    def email_index(self, email: str) -> str:
        return hmac.new(
            self._key,
            _EMAIL_INDEX_CONTEXT + _normalize_email(email).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()


class PlaintextFieldCipher:
    """Fallback when no key is configured; keeps the app usable but unprotected."""

    enabled = False

    def encrypt(self, value: str) -> str:
        return value

    def decrypt(self, value: str | None) -> str:
        return value or ""

    def email_index(self, email: str) -> str:
        return hashlib.sha256(
            _LEGACY_INDEX_CONTEXT + _normalize_email(email).encode("utf-8")
        ).hexdigest()


def _normalize_email(email: str) -> str:
    return email.strip().casefold()


def _decode_key(material: str) -> bytes:
    text = material.strip()
    if not text:
        raise ValueError("Encryption key is empty")
    candidates: list[bytes] = []
    try:
        candidates.append(base64.urlsafe_b64decode(text + "=" * (-len(text) % 4)))
    except (binascii.Error, ValueError):
        pass
    try:
        candidates.append(bytes.fromhex(text))
    except ValueError:
        pass
    for candidate in candidates:
        if len(candidate) == _KEY_BYTES:
            return candidate
    raise ValueError("Encryption key must decode to 32 bytes (base64 or hex)")


def build_field_cipher(key_material: str) -> FieldCipher:
    text = key_material.strip()
    if not text:
        logger.warning(
            "DATA_ENCRYPTION_KEY is unset; participant emails and transcripts are stored in plaintext"
        )
        return PlaintextFieldCipher()
    return AesFieldCipher(_decode_key(text))


@lru_cache
def get_field_cipher() -> FieldCipher:
    from app.config import get_settings

    return build_field_cipher(get_settings().data_encryption_key)
