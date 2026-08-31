from dataclasses import dataclass, field
from typing import Protocol

from app.guardrails.policy import GuardrailDecision, GuardrailPolicy
from app.llm.client import LLMError
from app.rag.contracts import RetrievedChunk, Retriever


class AnswerGenerator(Protocol):
    def generate(self, question: str, chunks: list[RetrievedChunk]) -> str: ...


class QueryRewriterProto(Protocol):
    def rewrite(self, question: str) -> str: ...


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
    """Apply guardrails and evidence thresholds; generate with an LLM when configured."""

    def __init__(
        self,
        guardrails: GuardrailPolicy,
        retriever: Retriever,
        minimum_score: float = 0.75,
        generator: AnswerGenerator | None = None,
        query_rewriter: QueryRewriterProto | None = None,
    ) -> None:
        self._guardrails = guardrails
        self._retriever = retriever
        self._minimum_score = minimum_score
        self._generator = generator
        self._query_rewriter = query_rewriter

    def answer(self, question: str) -> ChatResult:
        guardrail_result = self._guardrails.evaluate(question)
        if guardrail_result.decision is GuardrailDecision.BLOCK:
            return ChatResult(
                status="refused",
                reason=guardrail_result.reason,
                layer=guardrail_result.layer,
            )

        search_query = question
        if self._query_rewriter is not None:
            try:
                rewritten = self._query_rewriter.rewrite(question)
                if rewritten:
                    # Keep original terms too so rewrite misses do not drop hits.
                    search_query = f"{question}\n{rewritten}"
            except LLMError:
                search_query = question

        ranked = self._retriever.search(search_query)
        chunks = [chunk for chunk in ranked if chunk.score >= self._minimum_score]
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
