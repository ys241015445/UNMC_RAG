# Current Students Allowlist Scraper Design

**Date:** 2026-08-31  
**Branch:** `feat/scrape-current-students`  
**Status:** Approved

## Goals

Use a standalone script to scrape the [UNM Current Students](https://www.nottingham.edu.my/CurrentStudents/) portal and its public HTML subpages under the same-domain `/CurrentStudents/` prefix, producing structured materials that can be used directly as input for subsequent RAG ingestion or file uploads.

## Non-goals

- Do not integrate with FastAPI, pgvector, or the chat pipeline
- Do not download attachments such as PDF or Word files (record links only)
- Do not follow external links or expand the scope to the entire `nottingham.edu.my` site
- Do not bypass login walls or access content that requires authentication

## Scope

| Item | Value |
|----|-----|
| Seed URL | `https://www.nottingham.edu.my/CurrentStudents/` |
| Allowed host | `www.nottingham.edu.my` |
| Allowed path prefix | `/CurrentStudents/` |
| Content | HTML body text (with navigation noise removed) |
| Attachments | Record in `attachments.jsonl`; do not download |
| Default page limit | 200 (overridable via CLI) |

## Output Layout

```
data/scraped/current_students/
  pages/<slug>.md
  documents.jsonl
  index.json
  attachments.jsonl
  run_meta.json
```

`data/scraped/` is ignored by `.gitignore` to prevent full-site scrape results from entering version control.

## Record Fields

For each page document:

- `id`: stable short hash (based on the normalized URL)
- `url`: normalized URL
- `title`
- `section`: derived from breadcrumbs or the path
- `text`: plain-text body content
- `outbound_links`: HTML links under the same prefix
- `attachment_links`: attachment URLs discovered on the page
- `fetched_at`: ISO 8601 UTC
- `content_hash`: prefix of the body text's SHA-256 hash

Markdown: YAML front matter (`url` / `title` / `fetched_at` / `id`) + body content.

## Scraping Behavior

- BFS queue
- URL normalization: remove fragments; preserve query strings; normalize trailing slashes (retain `/` for directory pages)
- Default request interval: 0.75 seconds; the User-Agent identifies the UNMC_RAG research scraper
- Record non-HTML responses and 4xx–5xx errors in `run_meta.errors` without interrupting the run
- Attachment extensions: `.pdf` `.doc` `.docx` `.xls` `.xlsx` `.ppt` `.pptx` `.zip`

## Dependencies

Optional dependency group `scrape`: `httpx`, `beautifulsoup4`, and `lxml`. These are not included in the main application's runtime dependencies.

## Compliance

For preparing materials for an internal course-assistant pilot only; comply with the site's terms of service and use a reasonable request rate; copyright remains with the original site.
