"""OpenAI 兼容聊天客户端（智谱 GLM 等）。"""

from __future__ import annotations

from typing import Any

import httpx


class LLMError(RuntimeError):
    """模型调用失败。"""


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
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise LLMError("LLM response missing choices[0].message.content") from error

        if not isinstance(content, str) or not content.strip():
            raise LLMError("LLM returned empty content")
        return content.strip()
