# Study conditions (researchers only)

Do not link this page from the participant UI. Participants should only receive one opaque URL.

This is a 2×2 chatbot study: **competence** (low vs high) × **warmth** (low vs high). The four cells are selected by URL. The page chrome is the same on every path. Tone comes from the persona prompt, the opening line, refusal copy, and the sampling knobs in [`app/experiment/conditions.json`](../app/experiment/conditions.json).

Competence here is **wording**: confidence, fluency, and structure. Answers still have to stay inside retrieved campus evidence. The low-competence personas hedge and stay brief; they are not instructed to invent false campus facts.

## Path → condition

| Path | Condition id | Competence | Warmth |
|------|----------------|------------|--------|
| `/k7q2` | LL | low | low |
| `/m3x9` | LH | low | high |
| `/p8d4` | HL | high | low |
| `/t5w1` | HH | high | high |

Assignment is done by giving each participant one of these links. The app does not randomize and does not show the condition id, the words competence or warmth, or the other paths.

Restart the server after changing an entry path. Prompt text, openings, refusals, `temperature`, and `max_tokens` are read from the JSON file on each change (the file's modification time). Path segments are registered when the process starts, and they are also listed in `deploy/nginx.conf` so the Docker image proxies those four URLs to FastAPI.

## What participants see

Each path serves a multi-turn chat: a transcript, school-email field, and a composer. The transcript stays on the page and in `sessionStorage` for that path. Follow-up questions are sent to `POST /api/v1/chat/{path}/messages` with the saved `session_id`. The server loads that session's messages and sends them to the model with the path's system prompt.

The browser never receives `condition_id`. Refusal codes are stored in the database; the bubble shows the persona's refusal sentence from `refusals` in the JSON file.

## Editing personas

Edit [`app/experiment/conditions.json`](../app/experiment/conditions.json):

- `persona` — system-side voice. Not rendered in the page.
- `shared_rules` — appended to every persona. Keeps answers tied to the `[Evidence]` block.
- `opening_message` and `refusals` — participant-facing. The loader rejects text that contains `LL`/`LH`/`HL`/`HH`, `competence`, or `warmth`.
- `temperature` and `max_tokens` — passed through on grounded answers. Low-competence cells use a higher temperature and a shorter cap; high-competence cells stay cooler and can answer longer.

`UNMC_RAG_EXPERIMENT_HISTORY_MESSAGES` (default `16`) is how many prior user and assistant messages are included. `0` sends only the current question. Set `UNMC_RAG_EXPERIMENT_CONDITIONS_PATH` to point at a different JSON file.

## How conversations are stored

Apply [`supabase/migrations/20261104150000_create_experiment_conversations.sql`](../supabase/migrations/20261104150000_create_experiment_conversations.sql) in the Supabase SQL editor (or your usual migration path) before collecting data.

Tables live in the private `rag` schema, with row-level security enabled and no `anon` policies, matching `rag.document_chunks` and `rag.audit_events`.

`rag.chat_sessions`

- `id`
- `school_email` (normalized school address from `X-School-Email`)
- `condition_id` (`LL`, `LH`, `HL`, `HH`)
- `entry_path` (`k7q2`, `m3x9`, `p8d4`, `t5w1`)
- `created_at`, `updated_at`

`rag.chat_messages`

- `session_id`
- `school_email`, `condition_id`, `entry_path` (copied onto every row, including the opening line)
- `role` (`user` or `assistant`)
- `content`
- `status`, `reason`, `layer` (same guardrail outcome as the existing chat API; openings use `status = opening`)
- `citations` (jsonb)
- `created_at`, plus `seq` for order

The identity header is the same demo gate as the rest of this prototype. It is not SSO. Without `DATABASE_URL`, transcripts stay in process memory and disappear on restart.

Example once the API is running:

```bash
curl -s -X POST http://localhost:8000/api/v1/chat/k7q2/messages \
  -H 'Content-Type: application/json' \
  -H 'X-School-Email: student@unmc.edu' \
  -d '{"message":"When is the next graduation ceremony?"}'
```

A follow-up repeats `session_id` from that response. Load the thread with:

```bash
curl -s http://localhost:8000/api/v1/chat/k7q2/sessions/<session_id> \
  -H 'X-School-Email: student@unmc.edu'
```

Guardrails still run before retrieval. Prompt-injection checks look at the current message only. A follow-up that drops the topic word (for example "what about the date?" after a graduation question) is judged together with the previous user question, so the thread can continue. Weak evidence is still refused instead of guessed. Those replies use the cell's refusal copy so the voice stays consistent when the model is not called. Grounded answers go through the cell's system prompt with the saved history.

## Run locally

```bash
cp .env.example .env
# Set DATABASE_URL (Supabase session pooler) after applying the migration.
# Set LLM_API_KEY if you want model-written answers; otherwise grounded hits
# fall back to the retrieved passage text, and refusals still use the persona copy.

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open one link:

- http://localhost:8000/k7q2
- http://localhost:8000/m3x9
- http://localhost:8000/p8d4
- http://localhost:8000/t5w1

`/health` and `/ready` are unchanged. `/` remains the original single-shot course Q&A page.
