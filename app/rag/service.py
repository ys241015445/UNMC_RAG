from dataclasses import dataclass, field

from app.guardrails.policy import GuardrailDecision, GuardrailPolicy
from app.rag.contracts import Retriever


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
    """执行限域、证据阈值和带引用原型回答。"""

    def __init__(
        self,
        guardrails: GuardrailPolicy,
        retriever: Retriever,
        minimum_score: float = 0.75,
    ) -> None:
        self._guardrails = guardrails
        self._retriever = retriever
        self._minimum_score = minimum_score

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
        prototype_answer = "\n\n".join(chunk.text for chunk in chunks)
        return ChatResult(
            status="answered",
            reason="grounded_in_course_material",
            layer="output",
            answer=prototype_answer,
            citations=citations,
        )
