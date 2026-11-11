from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from app.llm.client import LLMError


class GuardrailDecision(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class GuardrailResult:
    decision: GuardrailDecision
    reason: str
    layer: str


class TopicClassifier(Protocol):
    def is_on_topic(self, question: str) -> bool: ...


class GuardrailPolicy:
    """Input injection rules plus topic gate (LLM classifier or keyword fallback)."""

    _injection_markers = (
        "ignore previous",
        "disregard previous",
        "system prompt",
        "reveal your instructions",
        "ignore all previous",
        "ignore the above",
    )
    _generic_terms = {"course", "teaching", "exam", "homework", "assignment"}

    def __init__(
        self,
        course_terms: set[str],
        *,
        topic_classifier: TopicClassifier | None = None,
    ) -> None:
        normalized_terms = {term.strip().casefold() for term in course_terms if term.strip()}
        self._course_terms = normalized_terms - self._generic_terms
        self._topic_classifier = topic_classifier

    def evaluate(self, question: str) -> GuardrailResult:
        normalized = " ".join(question.split()).casefold()

        if any(marker in normalized for marker in self._injection_markers):
            return GuardrailResult(GuardrailDecision.BLOCK, "prompt_injection", "input")

        if not normalized:
            return GuardrailResult(GuardrailDecision.BLOCK, "off_topic", "topic")

        if self._topic_classifier is not None:
            try:
                if self._topic_classifier.is_on_topic(question):
                    return GuardrailResult(
                        GuardrailDecision.ALLOW, "student_affairs_related", "topic"
                    )
                return GuardrailResult(GuardrailDecision.BLOCK, "off_topic", "topic")
            except LLMError:
                # Fall back to keywords if the model call fails.
                pass

        if not any(term in normalized for term in self._course_terms):
            return GuardrailResult(GuardrailDecision.BLOCK, "off_topic", "topic")

        return GuardrailResult(GuardrailDecision.ALLOW, "course_related", "topic")
