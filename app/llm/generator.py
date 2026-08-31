"""基于检索证据生成回答。"""

from __future__ import annotations

from app.llm.client import LLMError, OpenAICompatibleChatClient
from app.rag.contracts import RetrievedChunk

SYSTEM_PROMPT = (
    "你是校内课程与学生服务问答助手。只能根据提供的【证据】回答。"
    "若证据不足以回答，明确说无法根据现有材料确定，不要编造。"
    "回答简洁、准确；可使用用户提问的语言。不要输出与证据无关的内容。"
)


class EvidenceAnswerGenerator:
    def __init__(self, client: OpenAICompatibleChatClient) -> None:
        self._client = client

    @property
    def enabled(self) -> bool:
        return self._client.enabled

    def generate(self, question: str, chunks: list[RetrievedChunk]) -> str:
        evidence_blocks: list[str] = []
        for index, chunk in enumerate(chunks, start=1):
            evidence_blocks.append(
                f"[{index}] title={chunk.title}\n"
                f"source={chunk.source_id}\n"
                f"location={chunk.location}\n"
                f"text={chunk.text}"
            )
        evidence = "\n\n".join(evidence_blocks)
        user_prompt = (
            f"【问题】\n{question}\n\n"
            f"【证据】\n{evidence}\n\n"
            "请仅依据证据作答。"
        )
        return self._client.complete(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
        )


__all__ = ["EvidenceAnswerGenerator", "LLMError", "OpenAICompatibleChatClient"]
