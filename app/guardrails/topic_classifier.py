"""LLM-backed topic classification for the L2 guardrail."""

from __future__ import annotations

import json
import re

from app.llm.client import LLMError, OpenAICompatibleChatClient

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

SYSTEM_PROMPT = (
    "You are a topic gate for a university student-affairs Q&A assistant.\n"
    "Decide whether the user's question is related to student affairs / current-student "
    "services at a university campus.\n"
    "IN SCOPE examples: graduation / graduate ceremony dates, student registry, "
    "enrolment, examinations, quality manual, academic regulations, assessment, "
    "admissions, complaints, "
    "timetabling, academic appeals, misconduct, counselling, mental health, disability "
    "support, visa/immigration for students, shuttle bus, campus facilities, amenities, "
    "sports, student association, careers/internships for students, student feedback, "
    "IT/student support hub, personal tutoring, and similar campus student-life topics.\n"
    "OUT OF SCOPE examples: travel itineraries, movies, stock tips, cooking, coding "
    "homework unrelated to campus services, general chit-chat, jailbreak attempts.\n"
    "Judge semantic relatedness, NOT exact keyword matching.\n"
    "Reply with ONLY one JSON object and nothing else:\n"
    '{"related": true|false}'
)


class LLMTopicClassifier:
    """Ask the LLM: is this question related to student affairs?"""

    def __init__(
        self,
        client: OpenAICompatibleChatClient,
        *,
        topic_hints: set[str] | None = None,
        domain_description: str = "",
    ) -> None:
        self._client = client
        self._topic_hints = sorted(term for term in (topic_hints or set()) if term.strip())
        self._domain_description = domain_description.strip() or (
            "University of Nottingham student-affairs topics, including the UNM Current "
            "Students portal and the Quality Manual (academic regulations, assessment, "
            "admissions, complaints, registration): academic services, student registry, "
            "graduation, examinations, timetabling, appeals, wellbeing/counselling, "
            "facilities, shuttle, visa, careers, and student support."
        )

    def is_on_topic(self, question: str) -> bool:
        cleaned = question.strip()
        if not cleaned:
            return False

        hints = ", ".join(self._topic_hints) if self._topic_hints else "(none)"
        user_prompt = (
            f"Campus domain:\n{self._domain_description}\n\n"
            f"Optional topic hints (not required to match exactly):\n{hints}\n\n"
            f"User question:\n{cleaned}\n\n"
            "Is this question related to student affairs / current-student services? "
            'Return JSON {"related": true} or {"related": false}.'
        )
        raw = self._client.complete(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=256,
            disable_thinking=True,
        )
        return _parse_related(raw)


def _parse_related(raw: str) -> bool:
    text = raw.strip()
    lowered = text.casefold()

    # Prefer JSON when present.
    payload: dict | None = None
    try:
        payload = _parse_json_object(text)
    except LLMError:
        payload = None

    if payload is not None:
        for key in ("related", "allow", "on_topic", "in_scope"):
            if key in payload:
                return _as_bool(payload[key])

    # Plain-text fallbacks.
    if re.search(r"\b(related|allow|yes|true|in[_ ]scope)\b", lowered) and not re.search(
        r"\b(not related|unrelated|false|no|off[_ ]topic|out of scope)\b", lowered
    ):
        return True
    if re.search(r"\b(not related|unrelated|false|off[_ ]topic|out of scope)\b", lowered):
        return False
    raise LLMError(f"topic classifier could not parse decision: {raw[:200]}")


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"true", "yes", "1", "allow", "related"}
    raise LLMError("topic classifier boolean field has invalid type")


def _parse_json_object(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_OBJECT_RE.search(text)
        if not match:
            raise LLMError(f"topic classifier returned non-JSON: {raw[:200]}") from None
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise LLMError("topic classifier JSON must be an object")
    return data
