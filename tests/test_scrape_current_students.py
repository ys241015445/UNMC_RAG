from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "scrape_current_students.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("scrape_current_students", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


scrape = _load_module()
FIXTURE = ROOT / "tests" / "fixtures" / "current_students_sample.html"


def test_normalize_url_strips_fragment() -> None:
    url = "https://www.nottingham.edu.my/CurrentStudents/#welcome"
    assert scrape.normalize_url(url) == "https://www.nottingham.edu.my/CurrentStudents/"


def test_in_scope_allows_prefix_only() -> None:
    assert scrape.in_scope("https://www.nottingham.edu.my/CurrentStudents/")
    assert scrape.in_scope("https://www.nottingham.edu.my/CurrentStudents/Academic/Graduation.aspx")
    assert not scrape.in_scope("https://www.nottingham.edu.my/About/")
    assert not scrape.in_scope("https://example.com/CurrentStudents/")


def test_extract_page_from_fixture() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    page_url = "https://www.nottingham.edu.my/CurrentStudents/Academic/"
    record = scrape.extract_page(html, page_url)

    assert record.title == "Academic Services"
    assert "Find key resources" in record.text
    assert "Home" not in record.text
    assert "Copyright" not in record.text
    assert (
        "https://www.nottingham.edu.my/CurrentStudents/Academic/Graduation.aspx"
        in record.outbound_links
    )
    assert (
        "https://www.nottingham.edu.my/CurrentStudents/Academic/Exams.pdf"
        in record.attachment_links
    )
    assert all("example.com" not in link for link in record.outbound_links)
    assert all("/About/" not in link for link in record.outbound_links)


def test_write_outputs_creates_jsonl_and_markdown(tmp_path: Path) -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    record = scrape.extract_page(
        html, "https://www.nottingham.edu.my/CurrentStudents/Academic/"
    )
    scrape.write_outputs([record], out_dir=tmp_path, errors=[], seed=scrape.DEFAULT_SEED)

    documents = (tmp_path / "documents.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(documents) == 1
    index = (tmp_path / "index.json").read_text(encoding="utf-8")
    assert '"page_count": 1' in index
    attachments = (tmp_path / "attachments.jsonl").read_text(encoding="utf-8")
    assert "Exams.pdf" in attachments
    md_files = list((tmp_path / "pages").glob("*.md"))
    assert len(md_files) == 1
    assert "Academic Services" in md_files[0].read_text(encoding="utf-8")


def test_is_attachment() -> None:
    assert scrape.is_attachment("https://www.nottingham.edu.my/x/y.pdf")
    assert not scrape.is_attachment("https://www.nottingham.edu.my/CurrentStudents/x.aspx")
