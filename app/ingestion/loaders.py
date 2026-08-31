"""从抓取产物加载可切片文档。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LoadedDocument:
    source_id: str
    title: str
    url: str
    text: str


def load_documents_jsonl(path: Path) -> list[LoadedDocument]:
    if not path.is_file():
        raise FileNotFoundError(f"corpus not found: {path}")

    documents: list[LoadedDocument] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSONL at line {line_no}: {path}") from error

            source_id = str(payload.get("id") or "").strip()
            title = str(payload.get("title") or "").strip() or source_id or f"doc-{line_no}"
            url = str(payload.get("url") or "").strip()
            text = str(payload.get("text") or "").strip()
            if not source_id or not text:
                continue
            documents.append(
                LoadedDocument(source_id=source_id, title=title, url=url, text=text)
            )
    return documents
