# System Architecture

## Department-Level Internal Course RAG MVP

| Field | Content |
|------|------|
| Version | 0.1.0 |
| Deployment Model | Single-host Docker Compose |
| Runtime | Python 3.12 / FastAPI |

> **Scope Limitation Statement**: The architecture reduces the probability of out-of-scope responses through four gateway layers (input, topic, evidence, and output) and conservative refusal, but **cannot guarantee 100% scope enforcement**. Operations and product policies must be designed around being auditable, capable of refusing answers, and capable of taking content offline, rather than assuming that the model is absolutely controllable.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Browser                             │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI Application (app)                                     │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────┐ │
│  │ Web Templates│ │ REST API     │ │ Auth (Magic Link / SSO)  │ │
│  └──────────────┘ └──────────────┘ └──────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ RAG Orchestration: L1 Input → L2 Topic → Retrieval →        ││
│  │ L3 Evidence → LLM → L4 Output                               ││
│  └─────────────────────────────────────────────────────────────┘│
└────────────┬───────────────────────────────┬────────────────────┘
             │                               │
             ▼                               ▼
┌────────────────────────┐      ┌───────────────────────────────┐
│ PostgreSQL + pgvector   │      │ External Model API           │
│ Metadata/Vectors/Audit  │      │ (Chat/Embedding)              │
│                        │      │ OpenAI-compatible or          │
│                        │      │ department-approved endpoint  │
└────────────────────────┘      └───────────────────────────────┘
             │
             ▼
┌────────────────────────┐
│ Local Volume:          │
│ Uploads / Logs         │
└────────────────────────┘
```

---

## 2. Component Boundaries

| Component | Responsibilities | Out of Scope (Not Responsible For) |
|------|------|------------------|
| **Web/API Layer** (`app/api`) | HTTP routing and request validation; will later host template pages and sessions | No model training; no complex frontend SPA |
| **Authentication Module** (`app/auth`) | Magic-link issuance and validation, role injection; SSO adapter interface | The MVP does not implement a complete IdP |
| **Course Service** (`app/courses`) | Course CRUD, publication status, and permissions | No LMS enrollment synchronization |
| **Ingest Pipeline** (`app/ingestion`) | File parsing, chunking, Embedding calls, and vector writes | The MVP does not include a web crawler |
| **Retrieval and Generation Service** (`app/rag`) | pgvector retrieval, context construction, model calls, and citations | No federated retrieval across databases |
| **Scope Guardrail Gateway** (`app/guardrails`) | Targets L1–L4 policies and refusal codes; M0 implements L1/L2, while L3 resides in the Q&A service | M0 does not yet implement post-generation L4 validation |
| **Audit Module** (`app/audit`) | Persists Q&A and refusal events | No SIEM integration (export is supported) |
| **PostgreSQL** | Relational data, vector indexes, and transactions | Single instance; the MVP has no read/write separation |
| **External Model API** | Embedding and text generation | Availability and privacy are subject to provider constraints |

### 2.1 Authentication and Authorization Boundaries

- **MVP**: `@school.edu` magic link → session Cookie → role `{student, course_admin, sys_admin}`.
- **Production Version**: Add an OIDC implementation based on the interface in `app/auth/providers.py`, mapping tokens to the same internal `User` model.
- **Course Visibility**: All authenticated **students** can read **all published courses**; unpublished courses are visible only to administrators.

---

## 3. Data Flow

### 3.1 Document Ingestion (Upload-first)

```
Administrator uploads a file
    → API validation (type/size)
    → Store in uploads/{course_id}/
    → Parse (pdf/md/txt)
    → Chunk (configurable chunk_size and overlap)
    → Call Embedding API
    → Write to document_chunks + pgvector column
    → Update course ingest status
    → (Optional) Allow publication once conditions are met
```

### 3.2 Q&A (Four-Layer Scope Enforcement)

```
Student submits a question + optional course_id
    → [L1 Input] Rules/classification: injection, sensitive content, abuse?
         ├─ No  → Continue
         └─ Yes → Refuse (reason=L1_*)
    → [L2 Topic] Course scope + topic relevance
         ├─ Pass → Continue
         └─ No   → Refuse (reason=L2_*)
    → Top-K vector retrieval (restricted to published courses)
    → [L3 Evidence] Score threshold, coverage, minimum chunk count
         ├─ Pass → Continue
         └─ No   → Refuse or return excerpts only (reason=L3_*)
    → Assemble Prompt (chunks + citation IDs only)
    → Call external LLM API
    → [L4 Output] Validate: citations exist, no new facts, no prohibited language
         ├─ Pass → Return answer + citations
         └─ No   → Refuse (reason=L4_*)
    → Write to audit_events
```

### 3.3 Magic-Link Login

```
POST /auth/magic-link { email }
    → Validate school-domain suffix
    → Generate signed token (single-use, TTL)
    → Send email (the MVP may log the link)
GET /auth/verify?token=
    → Validate signature and expiration
    → Create/load User
    → Set-Cookie session
```

---

## 4. Directory Structure (Target Skeleton)

The current repository is a **runnable skeleton**. The following structure is the target MVP layout and will be implemented incrementally:

```
UNMC_RAG/
├── app/
│   ├── main.py                 # FastAPI entry point and health check
│   ├── config.py               # Environment configuration
│   ├── api/routes.py           # MVP HTTP endpoints
│   ├── auth/                   # Email policy and identity-provider interfaces
│   ├── guardrails/             # Input, topic, evidence, and output scope enforcement
│   ├── ingestion/              # Unified ingestion interfaces for files, LMS, and web
│   ├── models/                 # Future PostgreSQL domain models
│   └── rag/                    # Retrieval contracts, Q&A service, and citations
├── tests/                      # Unit and API tests
├── docs/
│   ├── PRD.md
│   └── architecture.md
├── supabase/migrations/        # pgvector + rag schema on Supabase
├── compose.yaml
├── Dockerfile
├── pyproject.toml
└── README.md
```

---

## 5. Deployment Topology

### 5.1 MVP: Single-Host Docker Compose

```yaml
# Target logical topology (illustrative for the database integration phase;
# not a verbatim copy of the current compose.yaml)
services:
  api:
    image: unmc-rag-api
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=postgresql+asyncpg://...
      - LLM_API_BASE=...
      - LLM_API_KEY=...
      - UNMC_RAG_SCHOOL_EMAIL_DOMAIN=school.edu
    volumes:
      - uploads:/app/uploads
    depends_on:
      db: { condition: service_healthy }

  db:
    image: pgvector/pgvector:pg16
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./deploy/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck: ...
```

| Node | Recommended Specification (200–2,000 Students) |
|------|---------------------------|
| CPU | 4 vCPU |
| Memory | 4–8 GB (Embedding is performed by an external API) |
| Disk | 100 GB+ SSD (documents + DB) |
| Network | Outbound access to the external model API |

Prerequisite: **Nginx/Caddy** terminates TLS (production); the departmental firewall permits outbound API access to the model service.

### 5.2 Network and Security Segmentation

```
Internet
   │
   ▼
[Reverse Proxy :443]
   │
   ▼
[API Container :8000] ──Internal Network──▶ [PostgreSQL :5432]
   │
   └──Outbound HTTPS──▶ [External Model API]
```

- The DB is not exposed to the public internet.
- Secrets are injected through `.env` or the department's secrets manager and are not included in image layers.

---

## 6. Scaling Path

| Stage | Trigger | Evolution |
|------|----------|------|
| **Vertical Scaling** | Increased latency, CPU saturation | Increase single-host resources; add uvicorn workers; tune the connection pool |
| **Read Scaling** | High retrieval QPS | PostgreSQL read replicas; short-lived retrieval-result cache (Redis, optional) |
| **Write Scaling** | ingest backlog | Asynchronous task queue (Celery/RQ + Redis); separate worker container |
| **Horizontal Application Scaling** | Concurrency > 50 | Multiple API instances + load balancing; sticky sessions or JWT; shared uploads volume/NFS |
| **High Availability** | Production SLA | DB primary/replica, backups, multiple AZs; health checks and automatic restarts |
| **Identity** | Departmental SSO requirement | Implement OIDC based on `auth/providers.py`, replacing the prototype identity entry point |
| **Knowledge Sources** | LMS integration | Add an LMS adapter under `ingestion/` without changing the RAG core |
| **Scope Enforcement Enhancement** | Spot checks reveal incorrect answers | Tighten thresholds, introduce a reranker, and add a human-review queue |

---

## 7. Key Decisions (ADR Summary)

### ADR-001: Single-Host Docker Compose as the MVP Deployment Unit

| Item | Content |
|----|------|
| **Status** | Accepted |
| **Context** | Departmental IT resources are limited, and a pilot must be launched quickly. |
| **Decision** | The MVP uses a single Compose stack (API + PostgreSQL/pgvector). |
| **Consequences** | No HA; recovery depends on backups; see Section 6 for the scaling path. |

### ADR-002: External Model API Instead of Self-Hosted Inference

| Item | Content |
|----|------|
| **Status** | Accepted |
| **Context** | GPU and MLOps costs are high; the department may already have an educational API contract. |
| **Decision** | Both Embedding and generation use external APIs; providers are abstracted through `llm_client`. |
| **Consequences** | Latency and cost depend on the provider; outbound network access and a DPA are required. |

### ADR-003: File Uploads First, LMS/Crawler Later

| Item | Content |
|----|------|
| **Status** | Accepted |
| **Context** | LMS integration has a long lead time; instructors can provide exported PDFs. |
| **Decision** | The first Ingest phase supports uploads only; a pluggable connector interface is reserved. |
| **Consequences** | Material updates depend on manual uploads; adding a connector later will not change the core tables. |

### ADR-004: Magic Links for the MVP, Replaceable with SSO

| Item | Content |
|----|------|
| **Status** | Accepted |
| **Context** | SSO integration depends on the departmental IdP schedule; the pilot must open as soon as possible. |
| **Decision** | Magic links are the default; `auth/providers` reserves support for OIDC. |
| **Consequences** | Links may be forwarded; the production version should migrate to SSO and shorten the token TTL. |

### ADR-005: Published Courses Are Visible to All Students

| Item | Content |
|----|------|
| **Status** | Accepted |
| **Context** | The MVP simplifies authorization; most departmental materials are shared internally. |
| **Decision** | No enrollment ACL is implemented; access distinguishes only draft/published status and roles. |
| **Consequences** | Sensitive courses must be published cautiously; the production version can restrict access by enrollment. |

### ADR-006: Four-Layer Scope Enforcement + Conservative Refusal, Without a 100% Guarantee

| Item | Content |
|----|------|
| **Status** | Accepted |
| **Context** | LLMs retain residual risks of hallucination and jailbreaks. |
| **Decision** | Implement L1–L4 in phases; M0 delivers L1–L3 first and completes L4 before integrating a generation model; always refuse when evidence is insufficient. |
| **Consequences** | Some answerable questions will be refused; operations must tune thresholds and conduct spot checks. |

### ADR-007: Unified Storage with PostgreSQL + pgvector

| Item | Content |
|----|------|
| **Status** | Accepted |
| **Context** | Reduce the number of components; vector workloads at a scale of 200–2,000 users are manageable. |
| **Decision** | Store metadata and vectors in the same database; select HNSW/IVFFlat indexes based on data volume. |
| **Consequences** | Very large scale will require a dedicated vector database or sharding; the MVP is adequately served. |

### ADR-008: FastAPI + Server-Side Template Pages

| Item | Content |
|----|------|
| **Status** | Accepted |
| **Context** | The department needs a lightweight UI while avoiding the maintenance cost of separate frontend and backend applications. |
| **Decision** | Use Jinja2 templates + minimal static assets; the API and pages run in the same process. |
| **Consequences** | Complex interactions are limited; if necessary, introduce an SPA later as the frontend only. |

---

## 8. Data Model (Core Tables, Illustrative)

| Table | Purpose |
|----|------|
| `users` | Email, role, creation time |
| `courses` | Code, name, term, status(draft/published) |
| `documents` | Associated course, file path, parsing status |
| `document_chunks` | Text, embedding vector, metadata JSON |
| `chat_sessions` / `chat_messages` | Optional conversation history |
| `audit_events` | Question, layer, reason_code, scores, citations |

---

## 9. Observability and Operations

| Item | MVP |
|----|-----|
| Health Check | The current `GET /health` checks whether the process is alive; add a separate readiness check after database integration |
| Logging | Structured JSON to stdout / volume |
| Metrics | Reserved Prometheus endpoint (optional P2) |
| Backups | Scheduled `pg_dump` task (documented; manual in the MVP) |

---

## 10. Mapping to the PRD

| PRD Section | Architectural Implementation |
|----------|----------|
| Four-layer scope enforcement | `app/guardrails/*` |
| Magic link / SSO | `app/auth/*` |
| File-upload ingest | `app/ingestion/*` |
| Published courses visible to all students | `courses.status` + retrieval filter |
| Non-functional requirement: 10–50 concurrent users | Single-host Compose + rate limiting + scaling path in Section 6 |

See [PRD.md](./PRD.md) for detailed product requirements.
