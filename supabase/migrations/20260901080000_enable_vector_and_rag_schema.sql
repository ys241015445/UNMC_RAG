-- Enable pgvector for later retrieval; keep application tables off the Data API.
create extension if not exists vector with schema extensions;

create schema if not exists rag;

create table rag.document_chunks (
  id uuid primary key default gen_random_uuid(),
  source_id text not null,
  title text not null default '',
  location text not null default '',
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index document_chunks_source_id_idx on rag.document_chunks (source_id);

create table rag.audit_events (
  id uuid primary key default gen_random_uuid(),
  question text not null,
  status text not null,
  reason text not null default '',
  layer text not null default '',
  scores jsonb not null default '{}'::jsonb,
  citations jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

alter table rag.document_chunks enable row level security;
alter table rag.audit_events enable row level security;

revoke all on schema rag from public;
revoke all on schema rag from anon, authenticated;
grant usage on schema rag to postgres, service_role;
grant all on all tables in schema rag to postgres, service_role;
alter default privileges in schema rag grant all on tables to postgres, service_role;
