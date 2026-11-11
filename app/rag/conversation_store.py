"""Per-email chat conversation persistence in Supabase Postgres.

Emails and transcripts are encrypted before they reach the database. Lookups go
through a keyed HMAC blind index so no plaintext address is ever queried.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.privacy.crypto import FieldCipher, get_field_cipher

MAX_MESSAGES = 200
MAX_MESSAGE_CHARS = 8000


def _sanitize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for message in messages[-MAX_MESSAGES:]:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        if role not in ("user", "assistant"):
            continue
        content = str(message.get("content", ""))[:MAX_MESSAGE_CHARS]
        entry: dict[str, Any] = {"role": role, "content": content}
        if message.get("status"):
            entry["status"] = str(message["status"])
        if message.get("reason"):
            entry["reason"] = str(message["reason"])
        if isinstance(message.get("citations"), list):
            entry["citations"] = message["citations"][:10]
        cleaned.append(entry)
    return cleaned


class InMemoryChatHistory:
    """Process-local chat history used when Postgres is not connected."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], dict[str, Any]] = {}

    async def list_conversations(self, email: str) -> list[dict[str, Any]]:
        rows = [row for (owner, _), row in self._rows.items() if owner == email]
        rows.sort(key=lambda row: row["updated_at"], reverse=True)
        return [
            {"id": row["id"], "title": row["title"], "updated_at": row["updated_at"]}
            for row in rows[:50]
        ]

    async def load_conversation(self, email: str, conversation_id: str) -> dict[str, Any] | None:
        row = self._rows.get((email, conversation_id))
        if row is None:
            return None
        return {
            "id": row["id"],
            "title": row["title"],
            "messages": list(row["messages"]),
            "updated_at": row["updated_at"],
        }

    async def save_conversation(
        self,
        email: str,
        conversation_id: str,
        title: str,
        messages: list[dict[str, Any]],
    ) -> None:
        self._rows[(email, conversation_id)] = {
            "id": conversation_id,
            "title": title[:120],
            "messages": _sanitize_messages(messages),
            "updated_at": datetime.now(UTC).isoformat(),
        }


class ConversationStore:
    """Thin asyncpg-backed store; all queries scoped by the email blind index."""

    def __init__(self, pool: Any, cipher: FieldCipher | None = None) -> None:
        self._pool = pool
        self._cipher = cipher or get_field_cipher()

    async def list_conversations(self, email: str) -> list[dict[str, Any]]:
        email_hash = self._cipher.email_index(email)
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(
                """
                select id, title, title_enc, updated_at
                from rag.chat_conversations
                where email_hash = $1
                order by updated_at desc
                limit 50
                """,
                email_hash,
            )
        return [
            {
                "id": row["id"],
                "title": self._cipher.decrypt(row["title_enc"]) or row["title"],
                "updated_at": row["updated_at"].isoformat(),
            }
            for row in rows
        ]

    async def load_conversation(self, email: str, conversation_id: str) -> dict[str, Any] | None:
        email_hash = self._cipher.email_index(email)
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select id, title, title_enc, messages, messages_enc, updated_at
                from rag.chat_conversations
                where email_hash = $1 and id = $2
                """,
                email_hash,
                conversation_id,
            )
        if row is None:
            return None
        if row["messages_enc"]:
            messages = json.loads(self._cipher.decrypt(row["messages_enc"]) or "[]")
        else:
            messages = row["messages"]
            if isinstance(messages, str):
                messages = json.loads(messages)
        return {
            "id": row["id"],
            "title": self._cipher.decrypt(row["title_enc"]) or row["title"],
            "messages": messages,
            "updated_at": row["updated_at"].isoformat(),
        }

    async def save_conversation(
        self,
        email: str,
        conversation_id: str,
        title: str,
        messages: list[dict[str, Any]],
    ) -> None:
        cleaned = _sanitize_messages(messages)
        email_hash = self._cipher.email_index(email)
        async with self._pool.acquire() as connection:
            await connection.execute(
                """
                insert into rag.chat_conversations
                    (id, email, email_enc, email_hash, title, title_enc, messages, messages_enc, updated_at)
                values ($1, '', $2, $3, '', $4, '[]'::jsonb, $5, now())
                on conflict (id) do update
                  set email = '',
                      email_enc = excluded.email_enc,
                      email_hash = excluded.email_hash,
                      title = '',
                      title_enc = excluded.title_enc,
                      messages = '[]'::jsonb,
                      messages_enc = excluded.messages_enc,
                      updated_at = now()
                where chat_conversations.email_hash = excluded.email_hash
                """,
                conversation_id,
                self._cipher.encrypt(email),
                email_hash,
                self._cipher.encrypt(title[:120]),
                self._cipher.encrypt(json.dumps(cleaned)),
            )
