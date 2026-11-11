-- Protect participant identifiers and transcripts with application-level
-- encryption. Plaintext columns stay in place so the shared reference project
-- keeps working; this project writes empty legacy values and fills the *_enc /
-- *_hash columns instead.

alter table rag.chat_conversations
    add column if not exists email_enc text,
    add column if not exists email_hash text,
    add column if not exists title_enc text,
    add column if not exists messages_enc text;

create index if not exists chat_conversations_email_hash_idx
    on rag.chat_conversations (email_hash, updated_at desc);

alter table rag.chat_sessions
    add column if not exists school_email_enc text,
    add column if not exists school_email_hash text;

create index if not exists chat_sessions_email_hash_idx
    on rag.chat_sessions (school_email_hash, condition_id, created_at desc);

alter table rag.chat_messages
    add column if not exists school_email_enc text,
    add column if not exists school_email_hash text,
    add column if not exists content_enc text;

create index if not exists chat_messages_email_hash_idx
    on rag.chat_messages (school_email_hash);
