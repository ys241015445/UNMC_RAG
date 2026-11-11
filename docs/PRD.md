# Product Requirements Document (PRD)

## Department-Level Internal Course RAG MVP

| Field | Content |
|------|------|
| Version | 0.1.0 (MVP Skeleton) |
| Status | Draft |
| Target User Base | 200–2,000 students |
| Peak Concurrency | 10–50 |

---

## 1. Background

The department needs a course-material-based question-answering capability for internal courses, helping students quickly retrieve syllabi, lecture notes, assignment instructions, and FAQs while preventing the model from improvising or answering content unrelated to the courses.

Existing solutions (general-purpose ChatGPT and public RAG platforms) present three types of problems:

1. **Uncontrollable identity and scope**: Access cannot be restricted to authenticated students, nor can knowledge be isolated by course or department.
2. **Cost and operational complexity**: Self-hosted large-model clusters or substantial SaaS subscriptions are unsuitable for departmental budgets and IT capabilities.
3. **Compliance risks**: Student questions and retrieval logs involve educational data and require institution-controlled storage and auditable policies.

This MVP uses a low-cost architecture based on **single-host Docker Compose + FastAPI + PostgreSQL/pgvector + external model APIs**, with **file upload** as the primary knowledge source. LMS synchronization and web crawling are planned for later iterations. Authentication uses **school email magic links**; the production version can replace this with institutional SSO without changing the core business model.

> **Important Notice**: The system uses four layers of scope control—input, topic, evidence, and output—together with a conservative refusal strategy, but **cannot guarantee 100% scope containment**. All answers must be verified against course materials. Users and administrators must understand the residual risks and support auditing and content governance.

---

## 2. Goals and Non-Goals

### 2.1 Goals

| ID | Goal |
|------|------|
| G1 | Authenticated students can ask questions about **all published courses** (the MVP does not implement enrollment-level ACLs). |
| G2 | Answers are based **only on ingested, published** course document chunks and include source citations. |
| G3 | **Conservatively refuse** out-of-scope questions, questions without evidence, and sensitive or compliance-risk content. |
| G4 | Allow administrators to upload and publish course documents and complete chunking, vectorization, and indexing. |
| G5 | A single-host deployment supports 200–2,000 students and peak concurrency of 10–50. |
| G6 | Log the question and retrieval process for auditing to meet basic departmental compliance requirements. |

### 2.2 Non-Goals (Not Included in the MVP)

| ID | Non-Goal |
|------|--------|
| NG1 | Full bidirectional LMS (Canvas/Moodle) integration and automatic synchronization. |
| NG2 | Multi-tenant, cross-department SaaS deployment or multi-region high-availability clusters. |
| NG3 | Local deployment or fine-tuning of large models; the MVP only calls **external model APIs**. |
| NG4 | Native mobile apps, advanced collaborative editing, or real-time multi-user whiteboards. |
| NG5 | A 100% hallucination-free or 100% scope-containment guarantee (see the Refusal Strategy and Risks sections). |
| NG6 | Restricting course visibility based on enrollment relationships (optional in the production version). |

---

## 3. Roles

| Role | Description | MVP Permissions |
|------|------|----------|
| **Student** | A currently enrolled student authenticated with a school email address | Browse the published course list; ask questions about any published course; view their own conversation history (optional) |
| **Course Admin** | Department faculty member or teaching assistant | Create/edit courses; upload documents; publish/unpublish courses; view Q&A statistics and refusal logs for their courses |
| **Sys Admin** | Department IT staff or project owner | Manage users and roles; configure model APIs, rate limits, and global policies; view system-wide audit logs |
| **Anonymous** | Unauthenticated user | Access only the login page and static information; **cannot** ask questions or perform retrieval |

---

## 4. User Stories

### 4.1 Authentication

- **US-A1**: As a student, I want to receive a magic link at my `@school.edu` email address so that I can log in without remembering a password.
- **US-A2**: As a Sys Admin, I want magic links to be single-use and short-lived so that the risk of link leakage is reduced.
- **US-A3 (Production)**: As an IT administrator, I want to replace the authentication module with institutional SSO/OIDC without rewriting the core Q&A logic.

### 4.2 Courses and Documents

- **US-C1**: As a Course Admin, I want to create courses and upload PDF/Markdown/TXT files so that student Q&A is grounded in evidence.
- **US-C2**: As a Course Admin, I want courses to be publishable only after document processing is complete so that students do not retrieve from an empty index.
- **US-C3**: As a student, I want to see all **published** courses so that I can consult department materials across courses.

### 4.3 Question Answering

- **US-Q1**: As a student, I want answers with **cited excerpts and document names** so that I can verify them against the source text.
- **US-Q2**: As a student, when a question is unrelated to any published course, I want the system to explicitly refuse rather than fabricate content.
- **US-Q3**: As a student, when the materials are insufficient to answer, I want to see a message such as "No supporting evidence found" instead of a guess.

### 4.4 Governance and Operations

- **US-O1**: As a Sys Admin, I want to view aggregate statistics for refusals and out-of-scope attempts so that I can adjust policies and training materials.
- **US-O2**: As a Course Admin, I want the index to update after documents are re-uploaded so that incorrect materials can be corrected during the semester.

---

## 5. Functional Requirements

### 5.1 Authentication and Sessions

| ID | Requirement | Priority |
|----|------|--------|
| FR-AUTH-01 | Allow magic-link requests only from school email addresses with configured domains | P0 |
| FR-AUTH-02 | Magic links are single-use and expire after 15 minutes by default | P0 |
| FR-AUTH-03 | Issue a session Cookie / Token after login and validate it server-side | P0 |
| FR-AUTH-04 | Reserve an OIDC/SSO adapter layer in the authentication interface (may be stubbed in the MVP) | P2 |

### 5.2 Course and Document Management

| ID | Requirement | Priority |
|----|------|--------|
| FR-COURSE-01 | Course CRUD: name, code, semester, description, and publication status | P0 |
| FR-COURSE-02 | Document upload: PDF, Markdown, and plain text; validate individual file size and type | P0 |
| FR-COURSE-03 | Asynchronous or synchronous pipeline: parse → chunk → vectorize → write to pgvector | P0 |
| FR-COURSE-04 | Publication gate: at least one vectorized document is required before publishing | P0 |
| FR-COURSE-05 | Authenticated students can list all **published** courses | P0 |

### 5.3 Retrieval and Generation

| ID | Requirement | Priority |
|----|------|--------|
| FR-RAG-01 | Vector retrieval + optional hybrid keyword retrieval (the MVP must support at least vector retrieval) | P0 |
| FR-RAG-02 | Restrict retrieval scope to the course selected by the user or the set of "all published courses" | P0 |
| FR-RAG-03 | Call an external model API to generate answers; the Prompt must enforce evidence citation | P0 |
| FR-RAG-04 | Response returns: `status`, `answer`, `citations[]`, `reason`, and `layer` | P0 |
| FR-RAG-05 | Global rate limiting: limit question frequency by user/IP | P1 |

### 5.4 Four-Layer Scope Control (Input, Topic, Evidence, Output)

| Layer | Description | MVP Behavior |
|------|------|----------|
| **L1 Input** | Intercept clearly out-of-scope, abusive, or prompt-injection input | Rules + lightweight classification; directly refuse high-risk input |
| **L2 Topic** | Determine whether the question falls within the topic space of published courses | Course metadata + retrieval confidence threshold |
| **L3 Evidence** | Require Top-K chunk scores and coverage to meet thresholds | Refuse or return excerpts only when thresholds are not met |
| **L4 Output** | Post-generation validation: determine whether content exceeds the evidence or contains prohibited language | Replace failed output with a refusal template |

### 5.5 Auditing and Observability

| ID | Requirement | Priority |
|----|------|--------|
| FR-AUDIT-01 | Record: user, course, question summary, refusal reason, citation ID, and model version | P0 |
| FR-AUDIT-02 | Health-check endpoint `/health`; PostgreSQL dependency readiness probe | P0 |
| FR-AUDIT-03 | Structured logs (JSON) for departmental log collection | P1 |

### 5.6 Lightweight Server-Rendered Pages

| ID | Requirement | Priority |
|----|------|--------|
| FR-UI-01 | FastAPI template pages: login, course list, and Q&A interface | P0 |
| FR-UI-02 | Admin pages: upload documents and publish courses (minimum viable functionality) | P1 |

---

## 6. Refusal Strategy

Design principle: **It is better to answer less than to answer incorrectly or out of scope**. The system **does not guarantee** 100% scope containment; the following strategies reduce the likelihood of failures while retaining audit evidence.

### 6.1 Hard Refusal

| Scenario | User-Facing Message (Example) |
|------|----------------------|
| Unauthenticated | "Please log in with your school email address first." |
| The input layer detects prompt injection, illegal content, hate, self-harm, etc. | "This question cannot be handled by this system." |
| Unrelated to the topics of all published courses (L2 failed) | "This question is outside the scope of published courses." |
| The highest retrieval score is below the threshold or no chunks are found (L3 failed) | "Insufficient supporting evidence was found in the course materials, so this question cannot be answered." |
| Output validation detects unsupported or out-of-scope statements (L4 failed) | "A reliable answer cannot be generated from the course materials." |
| External model API unavailable | "The service is temporarily unavailable. Please try again later." |

### 6.2 Soft Refusal / Degradation

| Scenario | Behavior |
|------|------|
| Evidence is partially relevant but insufficient for a complete answer | Return relevant excerpts + state that "the materials do not fully cover this question" |
| The question is too broad | Ask the user to specify a course or a more specific sub-question |

### 6.3 Refusal Metadata

Each refusal must record: `layer` (L1–L4), `reason_code`, optional `matched_course_ids`, and a retrieval-score summary for administrator review.

---

## 7. Data and Privacy

### 7.1 Data Classification

| Type | Example | Storage | Recommended Retention |
|------|------|------|----------|
| Account | School email address, role | PostgreSQL | Enrollment period + 1 year |
| Course Content | Uploaded files, chunks, vectors | PostgreSQL + object storage (optional local volume) | For the course lifecycle |
| Interaction | Questions, answers, citations, refusal records | PostgreSQL | 180 days by default (configurable) |
| Logs | Access, errors, rate limiting | Local log volume | 90 days |

### 7.2 Privacy Principles

1. **Data minimization**: Do not collect personal information unrelated to Q&A.
2. **Institution-controlled storage**: The MVP is deployed on a single host by default, and data remains on a department-controlled machine (the external model API still receives necessary context, which must be disclosed in departmental agreements).
3. **Student visibility**: During the MVP phase, students can view only their own conversations (if history is enabled); administrators can view aggregate statistics and do not view full text by default unless compliance approval is granted.
4. **Deletion and export**: The production version supports deletion and export by user/course; the MVP provides SQL-level operating instructions.

### 7.3 External Model API

- Content sent to third parties must be **trimmed to retrieved chunks + necessary context** to avoid uploading the entire corpus.
- Configuration items: `LLM_API_BASE`, `LLM_API_KEY`, model name, and maximum token count.
- The department must sign a DPA with the provider or use an approved education-compliant endpoint.

---

## 8. Security

| Area | MVP Requirement |
|------|----------|
| Transport | HTTPS terminates at the reverse proxy (production); HTTP may be used for local development |
| Authentication | HMAC-signed magic links; session HttpOnly Cookie |
| Authorization | Role-based endpoint protection; administrative operations require Course Admin / Sys Admin |
| Input | File-type allowlist, size limits, and path traversal protection |
| Injection | Parameterized SQL; fixed Prompt template structure; output-layer validation |
| Secrets | Inject through environment variables; never write to images or repositories |
| Rate Limiting | System-wide and per-user rate limits to prevent abuse and uncontrolled API costs |
| Dependencies | Regularly upgrade Python dependencies; CI runs `pytest` and lint |

---

## 9. Non-Functional Metrics

| Metric | MVP Target | Notes |
|------|----------|------|
| Peak Concurrent Users | 10–50 | Single-host Compose; configurable uvicorn workers |
| Registered Student Base | 200–2,000 | Index size grows linearly with document volume |
| Q&A P95 Latency | ≤ 8 s | Includes retrieval + external API; model-dependent |
| Retrieval P95 | ≤ 500 ms | pgvector, Top-K ≤ 10 |
| Availability | Best effort | No HA; planned maintenance windows are acceptable |
| Data Durability | Single database, single volume | The production version requires a backup strategy |
| Scope-Control Effectiveness | Measurable and iterative | **No 100% SLA**; refusal rate and manually sampled error rate are KPIs |

---

## 10. Acceptance Criteria

### 10.1 Functional Acceptance

- [ ] School email magic-link login succeeds; email addresses outside the school domain are rejected.
- [ ] A Course Admin can upload documents, and students can see the course after it is published.
- [ ] Students can ask questions about published courses and receive an answer with at least one citation when evidence exists.
- [ ] Unrelated questions and questions without evidence trigger L2/L3 refusals, and `reason_code` can be queried.
- [ ] Output-layer spot checks: clearly unsupported answers are intercepted by L4 (covered by test cases).
- [ ] `/health` returns 200 when the DB is ready.

### 10.2 Non-Functional Acceptance

- [ ] One-command Docker Compose startup: API + PostgreSQL (pgvector).
- [ ] No sustained 5xx responses at 10 concurrent users (for example, with a `locust`/`pytest` concurrency script).
- [ ] The audit table can retrieve all end-to-end fields for the most recent Q&A interaction.

### 10.3 Documentation Acceptance

- [ ] The README states "runnable skeleton, not a complete production system."
- [ ] architecture.md describes the four-layer scope control and deployment topology.
- [ ] Explicitly state that **100% scope containment cannot be guaranteed**.

---

## 11. Milestones

| Phase | Deliverables | Suggested Schedule |
|------|--------|--------------|
| **M0 Skeleton** | Repository structure, Compose, health check, placeholder routes | Week 1 |
| **M1 Authentication** | Magic links, sessions, role model | Week 2 |
| **M2 Ingest** | Upload, chunking, pgvector index | Weeks 3–4 |
| **M3 Q&A** | Retrieval, external API, citations, and L1–L4 refusals | Weeks 5–6 |
| **M4 Admin UI** | Minimal web pages, publication workflow, audit queries | Week 7 |
| **M5 Pilot** | Limited pilot with 1–2 courses, spot checks, and policy tuning | Week 8 |

---

## 12. Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|------|------|------|
| **Incomplete scope containment** | Incorrect answers, compliance incidents | Medium | Four-layer refusal, manual spot checks, rapid course unpublishing; documentation states there is no 100% guarantee |
| **External API context leakage** | Privacy | Medium | Minimal-chunk strategy, institution-approved providers, optional self-hosted proxy for redaction |
| **Hallucination** | Misleading students | Medium | Mandatory citations, L4 validation, low-temperature generation, refusal-first policy |
| **Peak concurrency above 50** | Latency, timeouts | Low–Medium | Rate limiting, queues, and a horizontal scaling path (see architecture) |
| **Poor document quality/OCR errors** | Retrieval noise | Medium | Upload standards, administrator preview, re-indexing |
| **Forwarded magic links** | Unauthorized access | Low | Short expiration, single use, optional device binding (production version) |
| **Single-host failure** | Service outage | Medium | Volume backups and a recovery runbook; HA in the production version |
| **Uncontrolled API costs** | Budget overrun | Medium | User rate limits, per-course quotas, and caching for frequently asked questions |

---

## Appendix: Glossary

| Term | Meaning |
|------|------|
| Scope Containment | Restricting Q&A to the materials and topic scope of published courses |
| Conservative Refusal | Refusing to generate when confidence is insufficient or validation fails, rather than guessing |
| Published Course | A course with `status=published` and at least one vectorized document |
