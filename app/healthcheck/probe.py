from dataclasses import dataclass
from typing import Any, Protocol

from app.rag.service import ChatResult, ChatService


@dataclass(frozen=True, slots=True)
class ProbeOutcome:
    ok: bool
    question: str
    reason: str
    status: str = ""
    layer: str = ""
    detail: str = ""


class FailureMailer(Protocol):
    def send_failure(self, outcome: ProbeOutcome) -> None: ...


def run_probe(chat_service: ChatService | Any, question: str) -> ProbeOutcome:
    try:
        result = chat_service.answer(question)
    except Exception as exc:
        return ProbeOutcome(
            ok=False,
            question=question,
            reason="exception",
            detail=f"{type(exc).__name__}: {exc}",
        )
    return _from_chat_result(question, result)


def notify_if_failed(outcome: ProbeOutcome, mailer: FailureMailer | None) -> bool:
    if outcome.ok or mailer is None:
        return False
    mailer.send_failure(outcome)
    return True


def _from_chat_result(question: str, result: ChatResult) -> ProbeOutcome:
    return ProbeOutcome(
        ok=result.status == "answered",
        question=question,
        reason=result.reason,
        status=result.status,
        layer=result.layer,
    )
