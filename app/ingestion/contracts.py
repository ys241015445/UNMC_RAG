from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SourceDocument:
    source_id: str
    course_id: str
    title: str
    content: bytes
    media_type: str
    version: str


class SourceAdapter(Protocol):
    """Shared interface for file upload, LMS, and allowlisted web collectors."""

    def fetch_changed(self, cursor: str | None) -> tuple[list[SourceDocument], str]: ...
