"""Generate answers from retrieved evidence."""

from __future__ import annotations

from collections.abc import Sequence

from app.llm.client import OpenAICompatibleChatClient
from app.rag.contracts import DialogueTurn, RetrievedChunk

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
        user_prompt = _evidence_user_prompt(question, chunks, voice=False)
        return self._client.complete(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
        )

    def generate_turn(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        *,
        system_prompt: str,
        history: Sequence[DialogueTurn],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Persona prompt plus saved transcript, then the current question and evidence."""

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt.strip() or SYSTEM_PROMPT}
        ]
        for turn in history:
            if turn.role in {"user", "assistant"} and turn.content.strip():
                messages.append({"role": turn.role, "content": turn.content})
        messages.append(
            {
                "role": "user",
                "content": _evidence_user_prompt(question, chunks, voice=True),
            }
        )
        return self._client.complete(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )


def _evidence_user_prompt(
    question: str,
    chunks: Sequence[RetrievedChunk],
    *,
    voice: bool,
) -> str:
    evidence_blocks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        evidence_blocks.append(
            f"[{index}] title={chunk.title}\n"
            f"source={chunk.source_id}\n"
            f"location={chunk.location}\n"
            f"text={chunk.text}"
        )
    evidence = "\n\n".join(evidence_blocks)
    closing = "Answer using only the evidence."
    if voice:
        closing = "Answer using only the evidence, in the voice set by your instructions."
    return f"[Question]\n{question}\n\n[Evidence]\n{evidence}\n\n{closing}"


__all__ = ["EvidenceAnswerGenerator", "OpenAICompatibleChatClient"]
