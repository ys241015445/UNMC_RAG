# UNMC RAG — Department-level on-campus course Q&A MVP

A low-cost, campus-deployable course-materials RAG (retrieval-augmented generation)
prototype for **200–2000 students** and **10–50 peak concurrent** users.

## Current status

> **This repository is a runnable skeleton, not a full production system.**

Already included:

- FastAPI app with `/health`, `/ready`, and `/api/v1/chat`
- School-email domain gate at the API boundary
- Prompt-injection / off-topic refusal, insufficient-evidence refusal, and citation shapes
- Coolify-ready all-in-one app image (nginx + FastAPI)
- Supabase Postgres (pgvector enabled; private `rag` schema)
- Automated tests for auth, guardrails, chat service, API, UI, ingest, and LLM client
- Product and architecture docs: [docs/PRD.md](./docs/PRD.md), [docs/architecture.md](./docs/architecture.md)
- Optional Current Students scraper, local keyword corpus retrieval, Jinja chat UI
- Optional Zhipu GLM (`glm-4.5-air`) grounded answer generation via OpenAI-compatible API

Still incomplete or left for you to finish:

- Full magic-link / SSO auth, upload ingest, four-layer guardrails end-to-end, and vector search
- Production HTTPS, backups, monitoring, SSO integration
- LMS / broader web connectors

The system uses an **input → topic → evidence → output** scoping strategy with
**conservative refusal**. It **cannot guarantee 100% scoping**. Read the
[PRD refusal strategy](./docs/PRD.md) and [architecture scoping statement](./docs/architecture.md)
before a pilot.

The chat API uses the `X-School-Email` header as a demo identity gate. That header
can be forged and is **for local development only**—do not expose it as real auth on
the public internet. Complete magic-link or campus SSO before any pilot.

---

## Docs

| Doc | Description |
|-----|-------------|
| [docs/PRD.md](./docs/PRD.md) | Product requirements: goals, stories, features, security, acceptance, milestones |
| [docs/architecture.md](./docs/architecture.md) | Architecture: boundaries, data flows, deploy topology, scale path, ADRs |

---

## MVP stack

| Layer | Choice |
|-------|--------|
| Language / framework | Python 3.12, FastAPI |
| Frontend | Lightweight server templates (Jinja2) |
| Database | Supabase Postgres + pgvector |
| Deploy | Docker Compose (local or Coolify) |
| Models | External Embedding / Chat API (optional; Zhipu GLM supported) |
| Knowledge sources | **File upload first**; LMS / web later; scraper prototype included |

Auth: **school-email magic link** (MVP plan); production may swap in campus SSO.

---

## Quick start

### Requirements

- Python **3.12+**
- Docker & Docker Compose v2
- A Supabase project (this repo is linked to `UNMC_RAG`)
- (Optional) department-approved model API key

### Local development

```bash
# Clone and enter the repo
git clone <repo-url> UNMC_RAG && cd UNMC_RAG

# Create a venv and install deps
python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -U pip
pip install -e ".[dev]"

# Environment (example)
cp .env.example .env
# Edit .env: paste DATABASE_URL from Supabase → Connect → Session pooler,
# plus LLM_API_KEY and school email domain.

# Run the API (dev, reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open the chat UI: <http://localhost:8000/>  
API docs: <http://localhost:8000/docs>.

Prototype curl:

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -H 'X-School-Email: student@unmc.edu' \
  -d '{"question":"What is a derivative in calculus?"}'
```

Without an indexed corpus (or when evidence is weak), course questions safely return
`insufficient_evidence`. With `LLM_API_KEY` set, topic gating and grounded answers both
use the configured chat model (`glm-4.5-air` by default).

### Docker Compose one-shot

Prepare `.env` (set `DATABASE_URL` from Supabase Session pooler, and `LLM_API_KEY`):

```bash
cp .env.example .env
# Edit .env: DATABASE_URL, LLM_API_KEY

docker compose -f docker-compose.yaml -f compose.local.yaml up -d --build
docker compose -f docker-compose.yaml -f compose.local.yaml ps
curl -s http://localhost:8080/health
curl -s http://localhost:8080/ready
```

Open <http://localhost:8080/>.  
One `app` container serves the UI on port 80 and proxies `/api`, `/health`, and `/ready` to FastAPI. Postgres is **Supabase**, not a Compose service.

### Supabase

Project: **UNMC_RAG** (`mqyqcoxzapzwkuxvctcv`, Tokyo / `ap-northeast-1`).

1. Open [Connect](https://supabase.com/dashboard/project/mqyqcoxzapzwkuxvctcv).
2. Copy **Session pooler** (port **5432**, IPv4 — required on Coolify/Tencent).
3. Put it in `.env` as `DATABASE_URL`. You can keep the `postgresql+asyncpg://` prefix; the app normalizes it.
4. Avoid `@ : / ? #` in the database password.

Coolify/Tencent hosts are typically IPv4-only, so do **not** use the direct `db.*.supabase.co:5432` URI unless the host has IPv6. Transaction pooler (port 6543) is for serverless; this container uses session mode.

Schema (already applied on the remote project):

- extension `vector` in `extensions`
- private schema `rag.document_chunks` and `rag.audit_events` (RLS on, no anon policies — backend uses the Postgres role)

### Tencent Cloud TCR (single app image)

Postgres is **not** in the app image; it stays on Supabase. Build and push:

```bash
# Personal TCR: ccr.ccs.tencentyun.com
# Enterprise TCR: <instance>.tencentcloudcr.com  (or the region endpoint shown in the console)
export TCR_REGISTRY=ccr.ccs.tencentyun.com
export TCR_NAMESPACE=your-namespace   # 镜像仓库命名空间
export TCR_IMAGE=unmc-rag
export TCR_TAG=latest

make docker-build TCR_NAMESPACE="$TCR_NAMESPACE"
docker login "$TCR_REGISTRY"          # 用户名为腾讯云账号 ID，密码为「访问凭证」token
make docker-push TCR_NAMESPACE="$TCR_NAMESPACE"
```

The pushed tag looks like `ccr.ccs.tencentyun.com/your-namespace/unmc-rag:latest`. That is only for a **registry pull** Coolify resource. GitHub App builds must not set `APP_IMAGE`.

### Coolify (GitHub App)

One GitHub repo → one Coolify resource → one container. nginx on **:80** serves the chat UI and proxies `/api`, `/health`, `/ready` to FastAPI on `127.0.0.1:8000`. Postgres stays on Supabase.

1. Resource type **Docker Compose**, branch **main**.
2. Compose file **`docker-compose.yaml`**. Never select `compose.local.yaml`.
3. **Do not set `APP_IMAGE`.**
4. Environment: paste [`.env.coolify.example`](./.env.coolify.example). Required: `DATABASE_URL`, `LLM_API_KEY`.
5. Domain → service **app**, container port **80**.
6. Healthcheck is in the compose file: `GET http://127.0.0.1:80/health` (start period 45s). Compose has no Healthchecks UI.
7. Redeploy. Open `/health` then the site root.

If the container is **Exited**, read **app** logs (not the build/helper container). Startup prints `[unmc-rag] starting uvicorn` / `starting nginx`.

### Tests

```bash
pytest
pytest --cov=app --cov-report=term-missing
ruff check app tests
```

### Scrape Current Students public pages (standalone)

Does not wire into the chat API by itself. Crawls HTML under
`www.nottingham.edu.my/CurrentStudents/`; PDF and other attachments are recorded as
links only.

```bash
pip install -e ".[scrape]"
python scripts/scrape_current_students.py \
  --out-dir data/scraped/current_students \
  --max-pages 200 \
  --delay 0.75
```

Outputs: `documents.jsonl`, `pages/*.md`, `index.json`, `attachments.jsonl`,
`run_meta.json` (directory is gitignored by default).

### Connect scraped corpus to the Q&A prototype

This stage uses **local keyword retrieval** (no embeddings / pgvector yet). Configure `.env`:

```bash
cp .env.example .env
# Confirm:
# UNMC_RAG_CORPUS_PATH=data/scraped/current_students/documents.jsonl
# UNMC_RAG_MINIMUM_RETRIEVAL_SCORE=0.3
# UNMC_RAG_COURSE_TERMS=...includes graduation,shuttle,etc...
# LLM_API_KEY=... LLM_MODEL=glm-4.5-air (optional grounded generation)

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Example:

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -H 'X-School-Email: student@unmc.edu' \
  -d '{"question":"When is the next graduation ceremony?"}'
```

If `UNMC_RAG_CORPUS_PATH` is unset or the file is missing, behavior matches the empty
retriever (insufficient evidence).

### Common environment variables

| Variable | Description |
|----------|-------------|
| `APP_IMAGE` | Optional TCR tag for `make docker-push` only. **Unset** on GitHub App Coolify |
| `DATABASE_URL` | Supabase Session pooler URI (`postgresql+asyncpg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres`) |
| `LLM_API_BASE` | External model API base (Zhipu default `https://open.bigmodel.cn/api/paas/v4/`) |
| `LLM_API_KEY` | API key (local `.env` only; never commit) |
| `LLM_MODEL` | Chat model name, e.g. `glm-4.5-air` |
| `UNMC_RAG_SCHOOL_EMAIL_DOMAIN` | Allowed school email domain |
| `UNMC_RAG_COURSE_TERMS` | Topic-gate keywords for the prototype |
| `UNMC_RAG_MINIMUM_RETRIEVAL_SCORE` | Minimum evidence score |
| `UNMC_RAG_CORPUS_PATH` | Path to local `documents.jsonl` for keyword retrieval |
| `UNMC_RAG_CHUNK_SIZE` / `CHUNK_OVERLAP` | Chunk size and overlap |
| `UNMC_RAG_RETRIEVAL_TOP_K` | Max chunks returned |

---

## Target layout

```
app/api/          # HTTP API
app/auth/         # Email policy and identity-provider interfaces
app/guardrails/   # Input and topic scoping
app/ingestion/    # File / LMS / web ingest interfaces
app/rag/          # Retrieval and chat orchestration
app/llm/          # External chat model client
app/web/          # Jinja UI routes (local uvicorn)
frontend/         # static chat page copied into the app image
tests/            # pytest
docs/             # PRD, architecture
deploy/           # nginx + container entrypoint
supabase/         # Postgres migrations (pgvector + rag schema)
docker-compose.yaml  # Coolify GitHub App
compose.local.yaml   # local 8080:80 only
Dockerfile           # nginx + FastAPI all-in-one
```

See [docs/architecture.md](./docs/architecture.md) for the full picture.

---

## License and compliance

Before deploying, confirm the external model API data-processing agreement, campus
personal-data rules, and course-material copyright / distribution scope. This MVP
documentation is not legal advice.

---

## Related links

- Product requirements: [docs/PRD.md](./docs/PRD.md)
- Architecture: [docs/architecture.md](./docs/architecture.md)
