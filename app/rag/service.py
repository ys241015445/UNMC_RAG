from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from app.guardrails.policy import GuardrailDecision, GuardrailPolicy
from app.llm.client import LLMError
from app.rag.contracts import DialogueTurn, RetrievedChunk, Retriever


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

        chunks = self._supporting_chunks(question)
        if not chunks:
            return ChatResult(
                status="refused",
                reason="insufficient_evidence",
                layer="evidence",
            )

        citations = self._citations_for(chunks)
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

    def answer_in_context(
        self,
        question: str,
        *,
        history: Sequence[DialogueTurn],
        system_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> ChatResult:
        """Answer one study turn with a persona prompt and prior transcript."""

        prior_user = ""
        for turn in reversed(history):
            if turn.role == "user" and turn.content.strip():
                prior_user = turn.content.strip()
                break

        guardrail_result = self._guardrail_for_turn(question, prior_user)
        if guardrail_result.decision is GuardrailDecision.BLOCK:
            return ChatResult(
                status="refused",
                reason=guardrail_result.reason,
                layer=guardrail_result.layer,
            )

        chunks = self._supporting_chunks(question, context_prefix=prior_user)
        if not chunks:
            return ChatResult(
                status="refused",
                reason="insufficient_evidence",
                layer="evidence",
            )

        citations = self._citations_for(chunks)
        if self._generator is None:
            answer = "\n\n".join(chunk.text for chunk in chunks)
        else:
            try:
                answer = self._generate_in_context(
                    question,
                    chunks,
                    history=history,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
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

    def _guardrail_for_turn(self, question: str, prior_user: str):
        """Keep injection checks on the current message.

        A short follow-up often drops the topic word. If the previous user
        question was in scope, judge the follow-up together with that question.
        """

        current = self._guardrails.evaluate(question)
        if current.decision is GuardrailDecision.ALLOW or current.reason != "off_topic":
            return current
        if not prior_user:
            return current
        contextual = self._guardrails.evaluate(f"{prior_user}\n{question}")
        if contextual.reason == "prompt_injection":
            return current
        return contextual

    def _supporting_chunks(
        self,
        question: str,
        *,
        context_prefix: str = "",
    ) -> list[RetrievedChunk]:
        search_query = question
        if self._query_rewriter is not None:
            try:
                rewritten = self._query_rewriter.rewrite(question)
                if rewritten:
                    # Keep original terms too so rewrite misses do not drop hits.
                    search_query = f"{question}\n{rewritten}"
            except LLMError:
                search_query = question
        if context_prefix:
            search_query = f"{context_prefix}\n{search_query}"
        ranked = self._retriever.search(search_query)
        return [chunk for chunk in ranked if chunk.score >= self._minimum_score]

    def _generate_in_context(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        *,
        history: Sequence[DialogueTurn],
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        generate_turn = getattr(self._generator, "generate_turn", None)
        if callable(generate_turn):
            return generate_turn(
                question,
                chunks,
                system_prompt=system_prompt,
                history=history,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        generator = self._generator
        if generator is None:
            raise RuntimeError("generator is not configured")
        return generator.generate(question, chunks)

    @staticmethod
    def _citations_for(chunks: list[RetrievedChunk]) -> list[Citation]:
        return [
            Citation(
                source_id=chunk.source_id,
                title=chunk.title,
                location=chunk.location,
            )
            for chunk in chunks
        ]
