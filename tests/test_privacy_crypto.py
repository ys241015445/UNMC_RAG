import base64
import os

import pytest

from app.privacy.crypto import AesFieldCipher, build_field_cipher, get_field_cipher


def _cipher() -> AesFieldCipher:
    key = base64.urlsafe_b64encode(os.urandom(32)).decode()
    built = build_field_cipher(key)
    assert isinstance(built, AesFieldCipher)
    return built


def test_ciphertext_hides_and_restores_the_value() -> None:
    cipher = _cipher()

    token = cipher.encrypt("11111111@unmc.edu")

    assert token.startswith("v1:")
    assert "11111111@unmc.edu" not in token
    assert cipher.decrypt(token) == "11111111@unmc.edu"


def test_encrypting_twice_uses_a_fresh_nonce() -> None:
    cipher = _cipher()

    assert cipher.encrypt("same question") != cipher.encrypt("same question")


def test_legacy_plaintext_rows_stay_readable() -> None:
    cipher = _cipher()

    assert cipher.decrypt("legacy plaintext") == "legacy plaintext"
    assert cipher.decrypt(None) == ""


def test_email_index_is_stable_and_normalized() -> None:
    cipher = _cipher()

    first = cipher.email_index("Student@UNMC.edu")
    second = cipher.email_index("  student@unmc.edu ")

    assert first == second
    assert first != cipher.email_index("other@unmc.edu")
    assert "student" not in first


def test_another_tenants_key_cannot_read_the_row() -> None:
    token = _cipher().encrypt("secret transcript")

    assert _cipher().decrypt(token) == ""


def test_missing_key_falls_back_to_plaintext() -> None:
    cipher = build_field_cipher("")

    assert cipher.enabled is False
    assert cipher.encrypt("value") == "value"
    assert cipher.decrypt("value") == "value"
    assert cipher.email_index("a@unmc.edu") == cipher.email_index("a@unmc.edu")


def test_key_accepts_base64_and_hex() -> None:
    raw = os.urandom(32)

    assert build_field_cipher(base64.urlsafe_b64encode(raw).decode()).enabled is True
    assert build_field_cipher(raw.hex()).enabled is True


def test_invalid_key_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_field_cipher("too-short")


def test_field_cipher_is_cached() -> None:
    assert get_field_cipher() is get_field_cipher()
