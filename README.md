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

## Psychology experiment (competence × warmth)

Four participant links share one multi-turn chat screen. The server picks the persona.
Participants are not shown condition names. Mapping and storage details:
[docs/experiment-conditions.md](./docs/experiment-conditions.md).
Prompts live in [app/experiment/conditions.json](./app/experiment/conditions.json).

| Path | Condition | Competence | Warmth |
|------|-----------|------------|--------|
| `/k7q2` | LL | low | low |
| `/m3x9` | LH | low | high |
| `/p8d4` | HL | high | low |
| `/t5w1` | HH | high | high |

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000/k7q2> (or `/m3x9`, `/p8d4`, `/t5w1`). The transcript stays on the page, and each follow-up is sent with that session's saved history. Every session and message is stored with the school email, condition id, and opaque path in `rag.chat_sessions` and `rag.chat_messages` (migration `supabase/migrations/20261104150000_create_experiment_conversations.sql`). Apply that migration before collecting data. Without `DATABASE_URL`, transcripts stay in process memory only.

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
docker compose ps
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

One GitHub repo → one Coolify resource → one container. nginx on **:80** proxies `/`, `/api`, `/health`, `/ready`, `/setting`, and the study paths (`/k7q2`, `/m3x9`, `/p8d4`, `/t5w1`) to FastAPI on `127.0.0.1:8000`. Postgres stays on Supabase.

1. Resource type **Docker Compose**, branch **main**.
2. Compose file **`docker-compose.yaml`**. It builds **`Dockerfile.coolify`** (nginx + FastAPI, both corpora). Never select `compose.local.yaml`. `compose.yaml` is the same stack if a resource is already pointed at that name.
3. **Do not set `APP_IMAGE`.**
4. Environment: paste [`.env.coolify.example`](./.env.coolify.example). Required: `DATABASE_URL`, `LLM_API_KEY`, and `UNMC_RAG_DATA_ENCRYPTION_KEY` (participant emails and transcripts are stored encrypted).
5. Domain → service **app**, container port **80**.
6. Docker / Coolify healthchecks stay off (they were marking the stack unhealthy during startup).
7. Redeploy. Open `/health`, then `/` and one study path.

If the container is **Exited**, read **app** logs. Startup prints `[unmc-rag] starting uvicorn` / `starting nginx`.

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
# UNMC_RAG_CORPUS_PATH=data/scraped/current_students/documents.jsonl,data/scraped/nfp/documents.jsonl
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

If `UNMC_RAG_CORPUS_PATH` is unset or none of the listed files exist, behavior matches
the empty retriever (insufficient evidence). Comma-separated paths are loaded together.

### Common environment variables

| Variable | Description |
|----------|-------------|
| `APP_IMAGE` | Local / `make docker-push` tag only. **Unset** on GitHub App Coolify |
| `DATABASE_URL` | Supabase Session pooler URI (`postgresql+asyncpg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres`) |
| `LLM_API_BASE` | External model API base (Zhipu default `https://open.bigmodel.cn/api/paas/v4/`) |
| `LLM_API_KEY` | API key (local `.env` only; never commit) |
| `LLM_MODEL` | Chat model name, e.g. `glm-4.5-air` |
| `UNMC_RAG_SCHOOL_EMAIL_DOMAIN` | Allowed school email domain |
| `UNMC_RAG_COURSE_TERMS` | Topic-gate keywords for the prototype |
| `UNMC_RAG_MINIMUM_RETRIEVAL_SCORE` | Minimum evidence score |
| `UNMC_RAG_CORPUS_PATH` | Comma-separated paths to local `documents.jsonl` files for keyword retrieval |
| `UNMC_RAG_CHUNK_SIZE` / `CHUNK_OVERLAP` | Chunk size and overlap |
| `UNMC_RAG_RETRIEVAL_TOP_K` | Max chunks returned |
| `UNMC_RAG_EXPERIMENT_HISTORY_MESSAGES` | Prior study-chat messages sent to the model (default 16) |
| `UNMC_RAG_EXPERIMENT_CONDITIONS_PATH` | Optional override for `app/experiment/conditions.json` |

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
deploy/              # nginx + container entrypoint
supabase/            # Postgres migrations (pgvector + rag schema)
docker-compose.yaml  # Coolify GitHub App
compose.yaml         # same stack, alternate filename
compose.local.yaml   # local 8080:80 only
Dockerfile.coolify   # Coolify image (nginx + FastAPI)
Dockerfile           # local / registry image
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
