"""Retriever implementations: empty placeholder and local keyword corpus search."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.ingestion.chunking import chunk_text
from app.ingestion.loaders import LoadedDocument, load_documents_jsonl
from app.rag.contracts import RetrievedChunk

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+")

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "am",
        "i",
        "me",
        "my",
        "we",
        "our",
        "you",
        "your",
        "he",
        "she",
        "it",
        "they",
        "them",
        "their",
        "this",
        "that",
        "these",
        "those",
        "and",
        "or",
        "but",
        "if",
        "then",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "from",
        "with",
        "as",
        "by",
        "about",
        "into",
        "over",
        "after",
        "before",
        "when",
        "where",
        "what",
        "which",
        "who",
        "whom",
        "how",
        "do",
        "does",
        "did",
        "can",
        "could",
        "should",
        "would",
        "will",
        "just",
        "please",
        "tell",
        "give",
        "next",
        "time",
    }
)

# Lightweight campus synonym / typo expansion for keyword retrieval.
_SYNONYMS: dict[str, set[str]] = {
    "graduation": {"graduate", "graduates", "graduating", "graduand", "graduands", "ceremony"},
    "graduate": {"graduation", "graduates", "graduating", "ceremony"},
    "graduates": {"graduation", "graduate", "graduating"},
    "graducation": {"graduation", "graduate", "ceremony"},
    "ceremony": {"graduation", "graduate"},
    "exam": {"examination", "exams", "examinations"},
    "exams": {"examination", "exam", "examinations"},
    "examination": {"exam", "exams", "examinations"},
    "timetable": {"timetabling", "schedule", "scheduling"},
    "timetabling": {"timetable", "schedule"},
    "counselling": {"counseling", "counsellor", "counselor", "wellbeing"},
    "counseling": {"counselling", "counsellor", "counselor", "wellbeing"},
    "wellbeing": {"well-being", "counselling", "counseling"},
    "shuttle": {"bus", "transport"},
    "visa": {"immigration"},
    "appeals": {"appeal"},
    "appeal": {"appeals"},
    "amenities": {"amenity", "food", "beverage"},
}


def stem_token(token: str) -> str:
    """Very light English stemming for campus FAQ matching."""
    stemmed = token
    for suffix in (
        "ation",
        "tions",
        "tion",
        "ments",
        "ment",
        "ness",
        "ings",
        "ing",
        "ies",
        "ied",
        "ers",
        "er",
        "ly",
        "ed",
        "es",
        "s",
    ):
        if len(stemmed) > len(suffix) + 3 and stemmed.endswith(suffix):
            stemmed = stemmed[: -len(suffix)]
            break
    return stemmed


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for match in _TOKEN_RE.findall(text):
        folded = match.casefold()
        if re.fullmatch(r"[\u4e00-\u9fff]+", folded):
            tokens.extend(list(folded))
            if len(folded) > 1:
                tokens.append(folded)
        else:
            tokens.append(folded)
    return tokens


def search_terms(text: str) -> set[str]:
    """Tokens used for retrieval: stopword-filtered, stemmed, synonym-expanded."""
    terms: set[str] = set()
    for token in tokenize(text):
        if token in _STOPWORDS or len(token) <= 1:
            continue
        candidates = {token, stem_token(token)}
        candidates |= _SYNONYMS.get(token, set())
        for syn in list(candidates):
            candidates |= _SYNONYMS.get(syn, set())
            candidates.add(stem_token(syn))
        terms |= {item for item in candidates if item and item not in _STOPWORDS}
    return terms


@dataclass(frozen=True, slots=True)
class _IndexedChunk:
    text: str
    source_id: str
    title: str
    location: str
    tokens: frozenset[str]


class EmptyRetriever:
    """Placeholder retriever that safely returns no evidence before a corpus is wired."""

    def search(self, question: str) -> list[RetrievedChunk]:
        return []


class LocalKeywordRetriever:
    """Prototype retriever without vectors: scores local chunks by question-token overlap."""

    def __init__(self, chunks: list[_IndexedChunk], *, top_k: int = 5) -> None:
        self._chunks = chunks
        self._top_k = top_k

    @classmethod
    def from_documents(
        cls,
        documents: list[LoadedDocument],
        *,
        chunk_size: int = 500,
        overlap: int = 80,
        top_k: int = 5,
    ) -> LocalKeywordRetriever:
        indexed: list[_IndexedChunk] = []
        for document in documents:
            pieces = chunk_text(document.text, chunk_size=chunk_size, overlap=overlap)
            for index, piece in enumerate(pieces, start=1):
                location = document.url or f"chunk-{index}"
                if len(pieces) > 1:
                    location = f"{location}#chunk-{index}"
                # Index both body and title so title phrases like "Graduation Ceremony" count.
                indexed_text = f"{document.title}\n{piece}"
                indexed.append(
                    _IndexedChunk(
                        text=piece,
                        source_id=document.source_id,
                        title=document.title,
                        location=location,
                        tokens=frozenset(search_terms(indexed_text)),
                    )
                )
        return cls(indexed, top_k=top_k)

    @classmethod
    def from_documents_jsonl(
        cls,
        path: Path,
        *,
        chunk_size: int = 500,
        overlap: int = 80,
        top_k: int = 5,
    ) -> LocalKeywordRetriever:
        return cls.from_documents(
            load_documents_jsonl(path),
            chunk_size=chunk_size,
            overlap=overlap,
            top_k=top_k,
        )

    def search(self, question: str) -> list[RetrievedChunk]:
        question_terms = search_terms(question)
        if not question_terms or not self._chunks:
            return []

        scored: list[RetrievedChunk] = []
        for chunk in self._chunks:
            overlap = question_terms & chunk.tokens
            if not overlap:
                continue
            score = len(overlap) / len(question_terms)
            scored.append(
                RetrievedChunk(
                    text=chunk.text,
                    source_id=chunk.source_id,
                    title=chunk.title,
                    location=chunk.location,
                    score=score,
                )
            )

        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[: self._top_k]
