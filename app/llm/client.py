"""OpenAI-compatible chat client (Zhipu GLM and similar)."""

from __future__ import annotations

from typing import Any

import httpx


class LLMError(RuntimeError):
    """Raised when a model call fails."""


class OpenAICompatibleChatClient:
    def __init__(
        self,
        *,
        api_base: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._api_base = api_base.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._transport = transport

    @property
    def enabled(self) -> bool:
        return bool(self._api_key.strip() and self._model.strip())

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        disable_thinking: bool = True,
    ) -> str:
        if not self.enabled:
            raise LLMError("LLM is not configured")

        url = f"{self._api_base}/chat/completions"
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        # GLM-4.5* may spend the whole budget on thinking and return empty content.
        if disable_thinking:
            payload["thinking"] = {"type": "disabled"}

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as error:
            raise LLMError(f"LLM HTTP error: {error}") from error
        except ValueError as error:
            raise LLMError(f"LLM response is not JSON: {error}") from error

        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as error:
            raise LLMError("LLM response missing choices[0].message") from error

        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str) and content.strip():
            return content.strip()

        # Some GLM builds put usable text only in reasoning_content.
        reasoning = message.get("reasoning_content") if isinstance(message, dict) else None
        if isinstance(reasoning, str) and reasoning.strip():
            return reasoning.strip()

        raise LLMError("LLM returned empty content")
