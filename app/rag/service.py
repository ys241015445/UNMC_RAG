import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from app.guardrails.policy import GuardrailDecision, GuardrailPolicy
from app.llm.client import LLMError
from app.rag.contracts import DialogueTurn, RetrievedChunk, Retriever
from app.rag.retrievers import stem_token, tokenize


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


_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_YEAR_RE = re.compile(r"\b20\d{2}\b")
_FOCUS_STOPS = frozenset(
    {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being", "am",
        "i", "me", "my", "we", "our", "you", "your", "he", "she", "it", "they",
        "them", "their", "this", "that", "these", "those", "and", "or", "but", "if",
        "of", "in", "on", "at", "to", "for", "from", "with", "as", "by", "about",
        "into", "over", "after", "before", "when", "where", "what", "which", "who",
        "how", "do", "does", "did", "can", "could", "should", "would", "will",
        "just", "please", "next", "there", "have", "has", "had", "not", "no",
    }
)
_MONTHS = frozenset(
    {
        "january", "february", "march", "april", "may", "june", "july", "august",
        "september", "october", "november", "december",
    }
)


def extractive_answer(question: str, chunks: list[RetrievedChunk]) -> str:
    """Pick campus sentences that overlap the question when no model is configured."""

    terms = _focus_terms(question)
    pool = _chunks_for_answer(chunks, terms)
    ranked: list[tuple[int, int, int, str]] = []
    for chunk_index, chunk in enumerate(pool):
        for sentence_index, sentence in enumerate(_sentences(chunk.text)):
            cleaned = _clean_sentence(sentence)
            if len(cleaned) < 40:
                continue
            score = _sentence_score(cleaned, question, terms)
            if score <= 0:
                continue
            ranked.append((score, chunk_index, sentence_index, cleaned))

    if not ranked:
        return " ".join(pool[0].text.split())[:700]

    ranked.sort(key=lambda item: (item[0], -item[1], -item[2]), reverse=True)
    chosen: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for _score, chunk_index, sentence_index, text in ranked:
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        chosen.append((chunk_index, sentence_index, text))
        if len(chosen) == 2:
            break
    chosen.sort()
    return " ".join(text for _chunk_index, _sentence_index, text in chosen)


def _chunks_for_answer(
    chunks: list[RetrievedChunk],
    terms: set[str],
) -> list[RetrievedChunk]:
    scored = [(_title_overlap(chunk.title, terms), chunk) for chunk in chunks]
    best = max((score for score, _chunk in scored), default=0)
    if best <= 0:
        return chunks
    return [chunk for score, chunk in scored if score == best]


def _title_overlap(title: str, terms: set[str]) -> int:
    if title.strip().startswith("-"):
        return 0
    return len(_focus_terms(title) & terms)


def _sentence_score(sentence: str, question: str, terms: set[str]) -> int:
    hits = len(_focus_terms(sentence) & terms)
    if hits == 0:
        return 0
    lowered = sentence.casefold()
    asked = question.casefold()
    bonus = 0
    if any(word in asked for word in ("when", "date")) and (
        _YEAR_RE.search(sentence) or any(month in lowered for month in _MONTHS)
    ):
        bonus += 3
    if "where" in asked and any(
        word in lowered for word in ("campus", "building", "room", "located", "centre", "center")
    ):
        bonus += 2
    if sentence.endswith((".", "!", "?")):
        bonus += 2
    else:
        bonus -= 2
    words = sentence.split()
    capitals = sum(1 for word in words if word[:1].isupper())
    if words and capitals >= max(4, int(len(words) * 0.45)):
        bonus -= 5
    return hits + bonus


def _focus_terms(text: str) -> set[str]:
    terms: set[str] = set()
    for token in tokenize(text):
        if token in _FOCUS_STOPS or len(token) <= 2:
            continue
        terms.add(token)
        terms.add(stem_token(token))
        if token.endswith("ies") and len(token) > 5:
            terms.add(token[:-3] + "y")
        elif token.endswith("s") and not token.endswith("ss") and len(token) > 4:
            terms.add(token[:-1])
    return terms


def _sentences(text: str) -> list[str]:
    return [part.strip(" -•\t") for part in _SENTENCE_RE.split(text) if part.strip()]


def _clean_sentence(sentence: str) -> str:
    collapsed = " ".join(sentence.split())
    # Drop a short heading glued to the next sentence, such as "Ceremony date The upcoming...".
    headed = re.match(r"^(\S+(?:\s+\S+){0,3})\s+([A-Z].{40,})$", collapsed)
    if headed and _heading_word(headed.group(1).split()[0]) and len(headed.group(1).split()) <= 4:
        collapsed = headed.group(2)
    words = collapsed.split()
    index = 0
    while (
        index < len(words) - 4
        and _heading_word(words[index])
        and _heading_word(words[index + 1])
    ):
        index += 1
    if index >= 2:
        return " ".join(words[index:])
    return collapsed


def _heading_word(word: str) -> bool:
    letters = [char for char in word if char.isalpha()]
    return bool(letters) and letters[0].isupper() and word[:1].isupper()


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
            answer = extractive_answer(question, chunks)
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
            focus = f"{prior_user}\n{question}" if prior_user else question
            answer = extractive_answer(focus, chunks)
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
