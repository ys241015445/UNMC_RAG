"""Normalize user questions into better keyword-search queries."""

from __future__ import annotations

import re

from app.llm.client import LLMError, OpenAICompatibleChatClient

SYSTEM_PROMPT = (
    "You rewrite campus student-affairs questions into a short English search query.\n"
    "Goals:\n"
    "1) Resolve follow-up questions against the recent conversation so they stand "
    "alone (e.g. 'What about postgraduates?' after a graduation-ceremony question "
    "-> 'postgraduate graduation ceremony date').\n"
    "2) Fix typos (e.g. graducation -> graduation).\n"
    "3) Expand morphology (graduate/graduates -> graduation ceremony date).\n"
    "4) Keep only useful retrieval keywords for campus docs.\n"
    "5) Prefer canonical terms: graduation, ceremony, date, shuttle, counselling, "
    "timetable, appeals, examination, visa, wellbeing, amenities, registry.\n"
    "Reply with ONLY the rewritten query text. No quotes, no JSON, no explanation."
)


class QueryRewriter:
    def __init__(self, client: OpenAICompatibleChatClient) -> None:
        self._client = client

    def rewrite(
        self, question: str, history: list[dict[str, str]] | None = None
    ) -> str:
        cleaned = " ".join(question.split())
        if not cleaned:
            return cleaned
        raw = self._client.complete(
            [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content": self._user_prompt(cleaned, history)}],
            temperature=0.0,
            max_tokens=64,
            disable_thinking=True,
        )
        rewritten = _clean_rewrite(raw)
        if not rewritten:
            raise LLMError("query rewriter returned empty text")
        return rewritten

    def _user_prompt(
        self, question: str, history: list[dict[str, str]] | None
    ) -> str:
        if not history:
            return f"Original question:\n{question}\n\nRewritten search query:"
        turns = history[-6:]
        transcript = "\n".join(
            f"{'Student' if message.get('role') == 'user' else 'Assistant'}: "
            f"{' '.join(str(message.get('content', '')).split())[:500]}"
            for message in turns
            if message.get("content")
        )
        return (
            f"Recent conversation:\n{transcript}\n\n"
            f"Latest question:\n{question}\n\n"
            "Rewritten standalone search query:"
        )


def _clean_rewrite(raw: str) -> str:
    text = raw.strip().strip('"').strip("'")
    text = re.sub(r"^(rewritten( search)? query|search query)\s*:\s*", "", text, flags=re.I)
    return " ".join(text.split())
