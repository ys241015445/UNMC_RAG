from dataclasses import dataclass, field
from typing import Protocol

from app.guardrails.policy import GuardrailDecision, GuardrailPolicy
from app.llm.client import LLMError
from app.rag.contracts import RetrievedChunk, Retriever


class AnswerGenerator(Protocol):
    def generate(self, question: str, chunks: list[RetrievedChunk]) -> str: ...


@dataclass(frozen=True, slots=True)
class Citation:
    source_id: str
    title: str
    location: str


@dataclass(frozen=True, slots=True)
class ChatResult:
    status: str
    reason: str
    layer: str
    answer: str = ""
    citations: list[Citation] = field(default_factory=list)


class ChatService:
    """执行限域、证据阈值，并在配置 LLM 时基于证据生成回答。"""

    def __init__(
        self,
        guardrails: GuardrailPolicy,
        retriever: Retriever,
        minimum_score: float = 0.75,
        generator: AnswerGenerator | None = None,
    ) -> None:
        self._guardrails = guardrails
        self._retriever = retriever
        self._minimum_score = minimum_score
        self._generator = generator

    def answer(self, question: str) -> ChatResult:
        guardrail_result = self._guardrails.evaluate(question)
        if guardrail_result.decision is GuardrailDecision.BLOCK:
            return ChatResult(
                status="refused",
                reason=guardrail_result.reason,
                layer=guardrail_result.layer,
            )

        chunks = [
            chunk
            for chunk in self._retriever.search(question)
            if chunk.score >= self._minimum_score
        ]
        if not chunks:
            return ChatResult(
                status="refused",
                reason="insufficient_evidence",
                layer="evidence",
            )

        citations = [
            Citation(
                source_id=chunk.source_id,
                title=chunk.title,
                location=chunk.location,
            )
            for chunk in chunks
        ]

        if self._generator is None:
            answer = "\n\n".join(chunk.text for chunk in chunks)
        else:
            try:
                answer = self._generator.generate(question, chunks)
            except LLMError:
                return ChatResult(
                    status="refused",
                    reason="generation_failed",
                    layer="output",
                    citations=citations,
                )

        return ChatResult(
            status="answered",
            reason="grounded_in_course_material",
            layer="output",
            answer=answer,
            citations=citations,
        )
