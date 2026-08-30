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
    """低成本第一层防线；生产版再接入主题分类器和红队样本。"""

    _injection_markers = (
        "忽略之前",
        "忽略以上",
        "忽略先前",
        "系统提示词",
        "system prompt",
        "reveal your instructions",
        "ignore previous",
        "disregard previous",
    )
    _generic_terms = {"课程", "教学", "考试", "作业"}

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
