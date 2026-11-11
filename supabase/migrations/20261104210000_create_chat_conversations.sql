-- Per-email chat history so students can revisit past conversations
-- from any device. The backend connects as the postgres role (RLS bypass);
-- no anon/authenticated policies, matching the existing rag tables.

create table if not exists rag.chat_conversations (
  id text primary key,
  email text not null,
  title text not null default '',
  messages jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists chat_conversations_email_idx
  on rag.chat_conversations (email, updated_at desc);

alter table rag.chat_conversations enable row level security;

revoke all on rag.chat_conversations from anon, authenticated;
grant all on rag.chat_conversations to postgres, service_role;
