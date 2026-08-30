from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    text: str
    source_id: str
    title: str
    location: str
    score: float


class Retriever(Protocol):
    def search(self, question: str) -> list[RetrievedChunk]: ...
