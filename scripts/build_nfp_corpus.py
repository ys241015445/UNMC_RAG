#!/usr/bin/env python3
"""Turn local NFP PDF and Excel files into a RAG documents.jsonl corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

SUPPORTED_SUFFIXES = {".pdf", ".xlsx"}


def document_id(name: str) -> str:
    return hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]


def clean_text(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def record_from_text(*, filename: str, text: str) -> dict[str, str] | None:
    cleaned = clean_text(text)
    if not cleaned:
        return None
    title = Path(filename).stem
    return {
        "id": document_id(filename),
        "url": filename,
        "title": title,
        "section": "NFP",
        "text": cleaned,
        "fetched_at": datetime.now(UTC).isoformat(),
    }


def pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def xlsx_text(path: Path) -> str:
    import openpyxl

    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    lines: list[str] = []
    for sheet in workbook.worksheets:
        lines.append(f"# {sheet.title}")
        for row in sheet.iter_rows(values_only=True):
            cells = [str(cell).strip() for cell in row if cell is not None and str(cell).strip()]
            if cells:
                lines.append(" | ".join(cells))
    workbook.close()
    return "\n".join(lines)


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return pdf_text(path)
    if suffix == ".xlsx":
        return xlsx_text(path)
    raise ValueError(f"unsupported file type: {path.name}")


def build_corpus(source_dir: Path, out_path: Path) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for path in sorted(source_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        record = record_from_text(filename=path.name, text=extract_text(path))
        if record is not None:
            records.append(record)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return records


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/scraped/nfp/documents.jsonl"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    records = build_corpus(args.source_dir, args.out)
    print(f"Wrote {len(records)} NFP documents to {args.out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
