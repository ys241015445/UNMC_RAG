import httpx

from app.llm.client import LLMError, OpenAICompatibleChatClient


def test_openai_compatible_client_parses_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).endswith("/chat/completions")
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": "  hello from glm  "}}
                ]
            },
        )

    client = OpenAICompatibleChatClient(
        api_base="https://open.bigmodel.cn/api/paas/v4/",
        api_key="test-key",
        model="glm-4.5-air",
        transport=httpx.MockTransport(handler),
    )
    assert client.complete([{"role": "user", "content": "hi"}]) == "hello from glm"


def test_client_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "unauthorized"}})

    client = OpenAICompatibleChatClient(
        api_base="https://open.bigmodel.cn/api/paas/v4/",
        api_key="bad",
        model="glm-4.5-air",
        transport=httpx.MockTransport(handler),
    )
    try:
        client.complete([{"role": "user", "content": "hi"}])
        raised = False
    except LLMError:
        raised = True
    assert raised is True
