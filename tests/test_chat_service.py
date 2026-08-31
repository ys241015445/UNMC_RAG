from app.guardrails.policy import GuardrailPolicy
from app.llm.client import LLMError
from app.rag.contracts import RetrievedChunk
from app.rag.service import ChatService


class StubRetriever:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self._chunks = chunks
        self.called = False

    def search(self, question: str) -> list[RetrievedChunk]:
        self.called = True
        return self._chunks


class StubGenerator:
    def __init__(self, text: str = "Evidence-based answer", *, fail: bool = False) -> None:
        self.text = text
        self.fail = fail
        self.called = False

    def generate(self, question: str, chunks: list[RetrievedChunk]) -> str:
        self.called = True
        if self.fail:
            raise LLMError("boom")
        return self.text


def test_refuses_off_topic_question_without_retrieval() -> None:
    retriever = StubRetriever([])
    service = ChatService(
        guardrails=GuardrailPolicy(course_terms={"calculus"}),
        retriever=retriever,
    )

    result = service.answer("Recommend a movie for me")

    assert result.status == "refused"
    assert result.reason == "off_topic"
    assert retriever.called is False


def test_refuses_when_course_evidence_is_insufficient() -> None:
    retriever = StubRetriever([])
    service = ChatService(
        guardrails=GuardrailPolicy(course_terms={"calculus"}),
        retriever=retriever,
    )

    result = service.answer("What is the exact date of the calculus exam?")

    assert result.status == "refused"
    assert result.reason == "insufficient_evidence"


def test_returns_grounded_prototype_answer_with_citation() -> None:
    retriever = StubRetriever(
        [
            RetrievedChunk(
                text="A derivative describes the instantaneous rate of change of a function.",
                source_id="math-01",
                title="Calculus Chapter 1",
                location="page 12",
                score=0.91,
            )
        ]
    )
    service = ChatService(
        guardrails=GuardrailPolicy(course_terms={"calculus", "derivative"}),
        retriever=retriever,
    )

    result = service.answer("What does a derivative mean in calculus?")

    assert result.status == "answered"
    assert "instantaneous rate of change" in result.answer
    assert result.citations[0].source_id == "math-01"


def test_uses_llm_generator_when_configured() -> None:
    retriever = StubRetriever(
        [
            RetrievedChunk(
                text="Graduation ceremonies are planned for 30-31 January 2027.",
                source_id="grad-1",
                title="Graduation",
                location="https://example.edu/grad",
                score=0.9,
            )
        ]
    )
    generator = StubGenerator("Next graduation is late January 2027.")
    service = ChatService(
        guardrails=GuardrailPolicy(course_terms={"graduation"}),
        retriever=retriever,
        generator=generator,
        minimum_score=0.3,
    )

    result = service.answer("When is the next graduation ceremony?")

    assert generator.called is True
    assert result.status == "answered"
    assert "January 2027" in result.answer


def test_uses_query_rewriter_for_retrieval() -> None:
    class Rewriter:
        def rewrite(self, question: str) -> str:
            return "graduation ceremony date"

    class AllowAllTopics:
        def is_on_topic(self, question: str) -> bool:
            return True

    retriever = StubRetriever(
        [
            RetrievedChunk(
                text="Graduation is planned for January 2027.",
                source_id="grad-1",
                title="Graduation",
                location="https://example.edu/grad",
                score=0.9,
            )
        ]
    )
    service = ChatService(
        guardrails=GuardrailPolicy(
            course_terms={"graduation"},
            topic_classifier=AllowAllTopics(),
        ),
        retriever=retriever,
        query_rewriter=Rewriter(),
        minimum_score=0.3,
    )
    result = service.answer("the next graduate time?")
    assert result.status == "answered"
    assert retriever.called is True
    assert "January 2027" in result.answer


def test_generation_failure_is_refused() -> None:
    retriever = StubRetriever(
        [
            RetrievedChunk(
                text="evidence",
                source_id="x",
                title="t",
                location="l",
                score=0.9,
            )
        ]
    )
    service = ChatService(
        guardrails=GuardrailPolicy(course_terms={"graduation"}),
        retriever=retriever,
        generator=StubGenerator(fail=True),
        minimum_score=0.3,
    )

    result = service.answer("graduation date?")
    assert result.status == "refused"
    assert result.reason == "generation_failed"
