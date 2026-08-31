"""Generate answers from retrieved evidence."""

from __future__ import annotations

from app.llm.client import OpenAICompatibleChatClient
from app.rag.contracts import RetrievedChunk

SYSTEM_PROMPT = (
    "You are a campus course and student-services Q&A assistant. "
    "Answer only from the provided [Evidence]. "
    "If the evidence is insufficient, say you cannot determine the answer from the "
    "available materials—do not invent facts. "
    "Be concise and accurate; reply in the same language as the user question. "
    "Do not add content unrelated to the evidence."
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
            f"[Question]\n{question}\n\n"
            f"[Evidence]\n{evidence}\n\n"
            "Answer using only the evidence."
        )
        return self._client.complete(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
        )


__all__ = ["EvidenceAnswerGenerator", "OpenAICompatibleChatClient"]
