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
    """文件上传、LMS 和白名单网页采集器遵循的统一接口。"""

    def fetch_changed(self, cursor: str | None) -> tuple[list[SourceDocument], str]: ...
