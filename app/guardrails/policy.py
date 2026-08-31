from dataclasses import dataclass
from enum import StrEnum


class GuardrailDecision(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class GuardrailResult:
    decision: GuardrailDecision
    reason: str
    layer: str


class GuardrailPolicy:
    """Low-cost first-pass guardrails; production can add classifiers and red-team sets."""

    _injection_markers = (
        "ignore previous",
        "disregard previous",
        "system prompt",
        "reveal your instructions",
        "ignore all previous",
        "ignore the above",
    )
    _generic_terms = {"course", "teaching", "exam", "homework", "assignment"}

    def __init__(self, course_terms: set[str]) -> None:
        normalized_terms = {term.strip().casefold() for term in course_terms if term.strip()}
        self._course_terms = normalized_terms - self._generic_terms

    def evaluate(self, question: str) -> GuardrailResult:
        normalized = " ".join(question.split()).casefold()

        if any(marker in normalized for marker in self._injection_markers):
            return GuardrailResult(GuardrailDecision.BLOCK, "prompt_injection", "input")

        if not normalized or not any(term in normalized for term in self._course_terms):
            return GuardrailResult(GuardrailDecision.BLOCK, "off_topic", "topic")

        return GuardrailResult(GuardrailDecision.ALLOW, "course_related", "topic")
