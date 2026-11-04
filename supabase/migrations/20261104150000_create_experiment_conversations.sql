-- Study transcripts. condition_id is for researchers only; do not add it to a public API.
-- Same privacy pattern as rag.document_chunks / rag.audit_events:
-- RLS on, no anon policies, backend uses the Postgres role (or unmc_rag_app).

create table rag.chat_sessions (
  id uuid primary key,
  school_email text not null,
  condition_id text not null,
  entry_path text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint chat_sessions_condition_id_chk
    check (condition_id in ('LL', 'LH', 'HL', 'HH')),
  constraint chat_sessions_entry_path_chk
    check (entry_path in ('k7q2', 'm3x9', 'p8d4', 't5w1'))
);

create index chat_sessions_email_condition_idx
  on rag.chat_sessions (school_email, condition_id, created_at);

create table rag.chat_messages (
  id uuid primary key,
  session_id uuid not null references rag.chat_sessions (id) on delete cascade,
  seq bigint generated always as identity,
  school_email text not null,
  condition_id text not null,
  entry_path text not null,
  role text not null,
  content text not null,
  status text not null default '',
  reason text not null default '',
  layer text not null default '',
  citations jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  constraint chat_messages_condition_id_chk
    check (condition_id in ('LL', 'LH', 'HL', 'HH')),
  constraint chat_messages_entry_path_chk
    check (entry_path in ('k7q2', 'm3x9', 'p8d4', 't5w1')),
  constraint chat_messages_role_chk
    check (role in ('user', 'assistant'))
);

create index chat_messages_session_seq_idx
  on rag.chat_messages (session_id, seq);

create index chat_messages_email_condition_idx
  on rag.chat_messages (school_email, condition_id, created_at);

alter table rag.chat_sessions enable row level security;
alter table rag.chat_messages enable row level security;

revoke all on rag.chat_sessions from public, anon, authenticated;
revoke all on rag.chat_messages from public, anon, authenticated;

grant all on rag.chat_sessions to postgres, service_role, unmc_rag_app;
grant all on rag.chat_messages to postgres, service_role, unmc_rag_app;
grant all on all sequences in schema rag to postgres, service_role, unmc_rag_app;

drop policy if exists app_all_chat_sessions on rag.chat_sessions;
create policy app_all_chat_sessions
  on rag.chat_sessions
  for all
  to unmc_rag_app
  using (true)
  with check (true);

drop policy if exists app_all_chat_messages on rag.chat_messages;
create policy app_all_chat_messages
  on rag.chat_messages
  for all
  to unmc_rag_app
  using (true)
  with check (true);
