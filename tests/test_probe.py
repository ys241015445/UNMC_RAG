from app.guardrails.policy import GuardrailPolicy
from app.healthcheck.probe import ProbeOutcome, notify_if_failed, run_probe
from app.rag.contracts import RetrievedChunk
from app.rag.service import ChatService


class StubRetriever:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self._chunks = chunks

    def search(self, question: str) -> list[RetrievedChunk]:
        return self._chunks


class ExplodingService:
    def answer(self, question: str) -> None:
        raise RuntimeError("llm down")


class RecordingMailer:
    def __init__(self) -> None:
        self.sent: list[ProbeOutcome] = []

    def send_failure(self, outcome: ProbeOutcome) -> None:
        self.sent.append(outcome)


def _service_with_chunks(chunks: list[RetrievedChunk]) -> ChatService:
    return ChatService(
        guardrails=GuardrailPolicy(course_terms={"graduation"}),
        retriever=StubRetriever(chunks),
        minimum_score=0.3,
    )


def test_probe_succeeds_when_chat_is_answered() -> None:
    service = _service_with_chunks(
        [
            RetrievedChunk(
                text="The upcoming graduation is planned for 30 January 2027.",
                source_id="grad-1",
                title="Graduation Ceremony",
                location="https://example.edu/grad",
                score=0.9,
            )
        ]
    )

    outcome = run_probe(service, "When is the next graduation ceremony?")

    assert outcome.ok is True
    assert outcome.status == "answered"
    assert outcome.question == "When is the next graduation ceremony?"


def test_probe_fails_when_chat_is_refused() -> None:
    service = _service_with_chunks([])

    outcome = run_probe(service, "When is the next graduation ceremony?")

    assert outcome.ok is False
    assert outcome.status == "refused"
    assert outcome.reason == "insufficient_evidence"


def test_probe_fails_when_chat_raises() -> None:
    outcome = run_probe(ExplodingService(), "When is the next graduation ceremony?")

    assert outcome.ok is False
    assert outcome.reason == "exception"
    assert "RuntimeError" in outcome.detail


def test_notify_if_failed_sends_only_on_failure() -> None:
    mailer = RecordingMailer()
    success = ProbeOutcome(ok=True, question="q", reason="answered", status="answered")
    failure = ProbeOutcome(ok=False, question="q", reason="insufficient_evidence", status="refused")

    assert notify_if_failed(success, mailer) is False
    assert notify_if_failed(failure, mailer) is True
    assert notify_if_failed(failure, None) is False
    assert mailer.sent == [failure]
