"""Idempotent DDL for the encrypted participant columns.

The SQL migration under supabase/migrations is the canonical record; this module
applies the same statements at startup so the shared database never serves a
query for a column that does not exist yet.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

PRIVACY_DDL = """
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
"""


async def ensure_privacy_columns(pool: Any) -> None:
    async with pool.acquire() as connection:
        await connection.execute(PRIVACY_DDL)
    logger.info("Encrypted participant columns are in place")
