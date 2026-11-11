# Current Students Scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Use a standalone script to scrape allowlisted HTML pages under `/CurrentStudents/`, outputting JSONL, Markdown, and an index while recording attachment links only.

**Architecture:** A CLI script performs BFS scraping; pure functions handle URL normalization, body extraction, and output; pytest tests extraction logic with a local HTML fixture and does not depend on external network access.

**Tech Stack:** Python 3.12, httpx, beautifulsoup4, lxml, pytest

## Global Constraints

- Restrict scraping to `www.nottingham.edu.my` and the `/CurrentStudents/` path prefix
- Do not download attachments or integrate with FastAPI/DB
- `data/scraped/` must be ignored by Git
- Put scraping dependencies in the optional `[scrape]` group; they need not be required for development

---

### Task 1: Scaffolding and Dependencies

**Files:**
- Modify: `pyproject.toml`
- Modify: `.gitignore`
- Create: `data/scraped/.gitkeep`
- Create: `scripts/scrape_current_students.py` (skeleton)

- [ ] Add optional `scrape` dependencies
- [ ] Ignore `data/scraped/*` while retaining `.gitkeep`
- [ ] Commit

### Task 2: Pure URL/Extraction Functions and Tests

**Files:**
- Create: `tests/fixtures/current_students_sample.html`
- Create: `tests/test_scrape_current_students.py`
- Modify: `scripts/scrape_current_students.py`

- [ ] Write failing tests for normalization, `in_scope`, `extract_page`, and attachment classification
- [ ] Implement the functions to make the tests pass
- [ ] Commit

### Task 3: BFS Scraper and Output

**Files:**
- Modify: `scripts/scrape_current_students.py`
- Modify: `README.md` (brief usage instructions)

- [ ] Implement fetching, BFS, and output to JSONL/MD/index/attachments/run_meta
- [ ] CLI: `--max-pages`, `--delay`, `--out-dir`, and `--seed`
- [ ] Run a local smoke test (network required)
- [ ] Commit
