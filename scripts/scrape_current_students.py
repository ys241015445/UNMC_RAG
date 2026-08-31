#!/usr/bin/env python3
"""白名单抓取 UNM Current Students 公开 HTML，输出 RAG 友好结构化材料。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import deque
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

DEFAULT_SEED = "https://www.nottingham.edu.my/CurrentStudents/"
ALLOWED_HOST = "www.nottingham.edu.my"
ALLOWED_PREFIX = "/CurrentStudents/"
ATTACHMENT_SUFFIXES = (
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".zip",
)
USER_AGENT = "UNMC-RAG-Scraper/0.1 (+local research; contact=campus-pilot)"
NOISE_SELECTORS = (
    "nav",
    "footer",
    "header",
    "script",
    "style",
    "noscript",
    ".global-nav",
    "#footer",
)


@dataclass(slots=True)
class PageRecord:
    id: str
    url: str
    title: str
    section: str
    text: str
    outbound_links: list[str] = field(default_factory=list)
    attachment_links: list[str] = field(default_factory=list)
    fetched_at: str = ""
    content_hash: str = ""


def normalize_url(url: str) -> str:
    raw = url.strip()
    if not raw:
        return ""
    cleaned, _frag = urldefrag(raw)
    parsed = urlparse(cleaned)
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    if path != "/" and not path.endswith("/") and "." not in Path(path).name:
        # Keep as-is for leaf paths without extension; directory-like paths often end with /
        pass
    if path != "/" and path.endswith("/index.aspx"):
        path = path[: -len("index.aspx")]
    if path != "/" and path.endswith("/index.html"):
        path = path[: -len("index.html")]
    # Collapse duplicate slashes in path
    path = re.sub(r"/{2,}", "/", path)
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def in_scope(url: str, *, host: str = ALLOWED_HOST, prefix: str = ALLOWED_PREFIX) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.netloc.lower() != host.lower():
        return False
    path = parsed.path or "/"
    return path == prefix.rstrip("/") or path.startswith(prefix)


def is_attachment(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(path.endswith(suffix) for suffix in ATTACHMENT_SUFFIXES)


def document_id(url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return digest[:16]


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def slug_for_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/") or "index"
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", path).strip("-").lower()
    if parsed.query:
        slug = f"{slug}-{document_id(url)[:8]}"
    return slug[:120] or document_id(url)


def _pick_main(soup: BeautifulSoup):
    for selector in ("main#content", "main", "#content", "article", ".content"):
        node = soup.select_one(selector)
        if node is not None:
            return node
    return soup.body or soup


def extract_page(html: str, page_url: str) -> PageRecord:
    soup = BeautifulSoup(html, "lxml")
    for selector in NOISE_SELECTORS:
        for node in soup.select(selector):
            node.decompose()

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        title = h1.get_text(strip=True) or title

    section = ""
    crumb = soup.select_one(".breadcrumb, .breadcrumbs, nav[aria-label='breadcrumb']")
    if crumb:
        section = " > ".join(part for part in crumb.stripped_strings if part)
    if not section:
        path = urlparse(page_url).path.strip("/")
        section = path.replace("/", " > ") if path else "CurrentStudents"

    main = _pick_main(soup)
    text = "\n".join(line.strip() for line in main.get_text("\n").splitlines() if line.strip())

    outbound: list[str] = []
    attachments: list[str] = []
    seen_out: set[str] = set()
    seen_att: set[str] = set()
    for anchor in main.find_all("a", href=True):
        absolute = normalize_url(urljoin(page_url, anchor["href"]))
        if not absolute:
            continue
        if is_attachment(absolute):
            if absolute not in seen_att:
                seen_att.add(absolute)
                attachments.append(absolute)
            continue
        if in_scope(absolute) and absolute not in seen_out:
            seen_out.add(absolute)
            outbound.append(absolute)

    fetched_at = datetime.now(UTC).isoformat()
    return PageRecord(
        id=document_id(page_url),
        url=normalize_url(page_url),
        title=title or slug_for_url(page_url),
        section=section,
        text=text,
        outbound_links=outbound,
        attachment_links=attachments,
        fetched_at=fetched_at,
        content_hash=content_hash(text),
    )


def render_markdown(record: PageRecord) -> str:
    front = (
        "---\n"
        f"id: {record.id}\n"
        f"url: {record.url}\n"
        f"title: {json.dumps(record.title, ensure_ascii=False)}\n"
        f"fetched_at: {record.fetched_at}\n"
        "---\n\n"
    )
    body = f"# {record.title}\n\n{record.text}\n"
    return front + body


def write_outputs(
    records: Iterable[PageRecord],
    *,
    out_dir: Path,
    errors: list[dict],
    seed: str,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    pages_dir = out_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    records_list = list(records)
    documents_path = out_dir / "documents.jsonl"
    attachments_path = out_dir / "attachments.jsonl"
    index_path = out_dir / "index.json"
    meta_path = out_dir / "run_meta.json"

    attachment_rows: list[dict] = []
    index_items: list[dict] = []

    with documents_path.open("w", encoding="utf-8") as docs_file:
        for record in records_list:
            docs_file.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
            md_path = pages_dir / f"{slug_for_url(record.url)}.md"
            md_path.write_text(render_markdown(record), encoding="utf-8")
            index_items.append(
                {
                    "id": record.id,
                    "url": record.url,
                    "title": record.title,
                    "section": record.section,
                    "markdown": str(md_path.relative_to(out_dir)),
                    "content_hash": record.content_hash,
                    "attachment_count": len(record.attachment_links),
                }
            )
            for link in record.attachment_links:
                attachment_rows.append(
                    {
                        "source_url": record.url,
                        "attachment_url": link,
                        "discovered_at": record.fetched_at,
                    }
                )

    with attachments_path.open("w", encoding="utf-8") as att_file:
        for row in attachment_rows:
            att_file.write(json.dumps(row, ensure_ascii=False) + "\n")

    index_path.write_text(
        json.dumps(
            {
                "seed": seed,
                "page_count": len(records_list),
                "attachment_count": len(attachment_rows),
                "pages": index_items,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    meta_path.write_text(
        json.dumps(
            {
                "seed": seed,
                "finished_at": datetime.now(UTC).isoformat(),
                "page_count": len(records_list),
                "error_count": len(errors),
                "errors": errors,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def crawl(
    *,
    seed: str = DEFAULT_SEED,
    max_pages: int = 200,
    delay: float = 0.75,
    timeout: float = 30.0,
) -> tuple[list[PageRecord], list[dict]]:
    seed_url = normalize_url(seed)
    if not in_scope(seed_url):
        raise ValueError(f"seed 不在白名单范围内: {seed_url}")

    queue: deque[str] = deque([seed_url])
    seen: set[str] = {seed_url}
    records: list[PageRecord] = []
    errors: list[dict] = []

    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    with httpx.Client(headers=headers, follow_redirects=True, timeout=timeout) as client:
        while queue and len(records) < max_pages:
            url = queue.popleft()
            try:
                response = client.get(url)
                content_type = response.headers.get("content-type", "")
                if response.status_code >= 400:
                    errors.append(
                        {"url": url, "error": f"HTTP {response.status_code}", "kind": "http"}
                    )
                    continue
                if "html" not in content_type.lower() and not url.lower().endswith(
                    (".aspx", ".html", ".htm", "/")
                ):
                    errors.append(
                        {
                            "url": url,
                            "error": f"non-html content-type: {content_type}",
                            "kind": "content-type",
                        }
                    )
                    continue
                final_url = normalize_url(str(response.url))
                if not in_scope(final_url):
                    errors.append(
                        {
                            "url": url,
                            "error": f"redirected out of scope: {final_url}",
                            "kind": "scope",
                        }
                    )
                    continue
                record = extract_page(response.text, final_url)
                records.append(record)
                for link in record.outbound_links:
                    if link not in seen and in_scope(link) and not is_attachment(link):
                        seen.add(link)
                        queue.append(link)
            except Exception as exc:  # noqa: BLE001 - 单页失败不中断整次运行
                errors.append({"url": url, "error": str(exc), "kind": "exception"})
            if delay > 0 and queue and len(records) < max_pages:
                time.sleep(delay)

    return records, errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/scraped/current_students"),
    )
    parser.add_argument("--max-pages", type=int, default=200)
    parser.add_argument("--delay", type=float, default=0.75)
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    records, errors = crawl(
        seed=args.seed,
        max_pages=args.max_pages,
        delay=args.delay,
        timeout=args.timeout,
    )
    write_outputs(records, out_dir=args.out_dir, errors=errors, seed=normalize_url(args.seed))
    print(
        f"抓取完成: pages={len(records)} errors={len(errors)} out={args.out_dir.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
