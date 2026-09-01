"""Normalize user questions into better keyword-search queries."""

from __future__ import annotations

import re

from app.llm.client import LLMError, OpenAICompatibleChatClient

SYSTEM_PROMPT = (
    "You rewrite campus student-affairs questions into a short English search query.\n"
    "Goals:\n"
    "1) Fix typos (e.g. graducation -> graduation).\n"
    "2) Expand morphology (graduate/graduates -> graduation ceremony date).\n"
    "3) Keep only useful retrieval keywords for campus docs.\n"
    "4) Prefer canonical terms: graduation, ceremony, date, shuttle, counselling, "
    "timetable, appeals, examination, visa, wellbeing, amenities, registry.\n"
    "Reply with ONLY the rewritten query text. No quotes, no JSON, no explanation."
)


class QueryRewriter:
    def __init__(self, client: OpenAICompatibleChatClient) -> None:
        self._client = client

    def rewrite(self, question: str) -> str:
        cleaned = " ".join(question.split())
        if not cleaned:
            return cleaned
        raw = self._client.complete(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (f"Original question:\n{cleaned}\n\nRewritten search query:"),
                },
            ],
            temperature=0.0,
            max_tokens=64,
            disable_thinking=True,
        )
        rewritten = _clean_rewrite(raw)
        if not rewritten:
            raise LLMError("query rewriter returned empty text")
        return rewritten


def _clean_rewrite(raw: str) -> str:
    text = raw.strip().strip('"').strip("'")
    text = re.sub(r"^(rewritten( search)? query|search query)\s*:\s*", "", text, flags=re.I)
    return " ".join(text.split())
