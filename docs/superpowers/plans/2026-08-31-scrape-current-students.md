# Current Students Scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 独立脚本抓取 `/CurrentStudents/` 白名单 HTML 页，输出 JSONL + Markdown + 索引，附件只记链接。

**Architecture:** CLI 脚本 BFS 抓取；纯函数负责 URL 规范化、正文抽取与写出；pytest 用本地 HTML fixture 测抽取逻辑，不依赖外网。

**Tech Stack:** Python 3.12、httpx、beautifulsoup4、lxml、pytest

## Global Constraints

- 仅 `www.nottingham.edu.my` + 路径前缀 `/CurrentStudents/`
- 不下载附件；不接入 FastAPI/DB
- `data/scraped/` 必须 gitignore
- 抓取依赖放在 optional `[scrape]`，dev 可不强制

---

### Task 1: 脚手架与依赖

**Files:**
- Modify: `pyproject.toml`
- Modify: `.gitignore`
- Create: `data/scraped/.gitkeep`
- Create: `scripts/scrape_current_students.py`（骨架）

- [ ] 增加 `scrape` optional deps
- [ ] ignore `data/scraped/*` 并保留 `.gitkeep`
- [ ] Commit

### Task 2: URL / 抽取纯函数 + 测试

**Files:**
- Create: `tests/fixtures/current_students_sample.html`
- Create: `tests/test_scrape_current_students.py`
- Modify: `scripts/scrape_current_students.py`

- [ ] 写失败测试：normalize、in_scope、extract_page、attachment 分类
- [ ] 实现使测试通过
- [ ] Commit

### Task 3: BFS 爬虫与写出

**Files:**
- Modify: `scripts/scrape_current_students.py`
- Modify: `README.md`（简短用法）

- [ ] 实现 fetch + BFS + 写出 JSONL/MD/index/attachments/run_meta
- [ ] CLI：`--max-pages`、`--delay`、`--out-dir`、`--seed`
- [ ] 本地试跑（网络）
- [ ] Commit
