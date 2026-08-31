"""Retriever implementations: empty placeholder and local keyword corpus search."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.ingestion.chunking import chunk_text
from app.ingestion.loaders import LoadedDocument, load_documents_jsonl
from app.rag.contracts import RetrievedChunk

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+")


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
                indexed.append(
                    _IndexedChunk(
                        text=piece,
                        source_id=document.source_id,
                        title=document.title,
                        location=location,
                        tokens=frozenset(tokenize(piece)),
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
        question_tokens = set(tokenize(question))
        if not question_tokens or not self._chunks:
            return []

        scored: list[RetrievedChunk] = []
        for chunk in self._chunks:
            overlap = question_tokens & chunk.tokens
            if not overlap:
                continue
            score = len(overlap) / len(question_tokens)
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
