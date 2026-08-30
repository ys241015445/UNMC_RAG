from app.guardrails.policy import GuardrailPolicy
from app.rag.contracts import RetrievedChunk
from app.rag.service import ChatService


class StubRetriever:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self._chunks = chunks
        self.called = False

    def search(self, question: str) -> list[RetrievedChunk]:
        self.called = True
        return self._chunks


def test_refuses_off_topic_question_without_retrieval() -> None:
    retriever = StubRetriever([])
    service = ChatService(
        guardrails=GuardrailPolicy(course_terms={"高等数学"}),
        retriever=retriever,
    )

    result = service.answer("给我推荐一部电影")

    assert result.status == "refused"
    assert result.reason == "off_topic"
    assert retriever.called is False


def test_refuses_when_course_evidence_is_insufficient() -> None:
    retriever = StubRetriever([])
    service = ChatService(
        guardrails=GuardrailPolicy(course_terms={"高等数学"}),
        retriever=retriever,
    )

    result = service.answer("高等数学考试的具体日期是什么？")

    assert result.status == "refused"
    assert result.reason == "insufficient_evidence"


def test_returns_grounded_prototype_answer_with_citation() -> None:
    retriever = StubRetriever(
        [
            RetrievedChunk(
                text="导数描述函数在某一点的瞬时变化率。",
                source_id="math-01",
                title="高等数学第一章",
                location="第 12 页",
                score=0.91,
            )
        ]
    )
    service = ChatService(
        guardrails=GuardrailPolicy(course_terms={"高等数学", "导数"}),
        retriever=retriever,
    )

    result = service.answer("高等数学中的导数表示什么？")

    assert result.status == "answered"
    assert "瞬时变化率" in result.answer
    assert result.citations[0].source_id == "math-01"
