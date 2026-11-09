"""Session and message storage for the study chatbot.

Postgres writes go to the private `rag` schema. When `DATABASE_URL` is unset,
an in-memory store keeps local UI sessions working; those rows vanish on restart.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

import asyncpg
from fastapi import Request


@dataclass(frozen=True, slots=True)
class SessionRecord:
    id: str
    school_email: str
    condition_id: str
    entry_path: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class MessageRecord:
    id: str
    session_id: str
    school_email: str
    condition_id: str
    entry_path: str
    role: str
    content: str
    status: str
    reason: str
    layer: str
    citations: tuple[dict[str, str], ...]
    created_at: datetime


class ConversationStore(Protocol):
    async def create_session(
        self,
        *,
        school_email: str,
        condition_id: str,
        entry_path: str,
        opening_message: str,
    ) -> SessionRecord: ...

    async def get_session(self, session_id: str) -> SessionRecord | None: ...

    async def list_sessions(
        self,
        school_email: str,
        entry_path: str | None = None,
    ) -> list[SessionRecord]: ...

    async def list_messages(self, session_id: str) -> list[MessageRecord]: ...

    async def append_message(
        self,
        *,
        session_id: str,
        school_email: str,
        condition_id: str,
        entry_path: str,
        role: str,
        content: str,
        status: str,
        reason: str,
        layer: str,
        citations: list[dict[str, str]],
    ) -> MessageRecord: ...


class InMemoryConversationStore:
    """Process-local stand-in used in tests and when Postgres is not configured."""

    def __init__(self) -> None:
        self.sessions: dict[str, SessionRecord] = {}
        self._messages: dict[str, list[MessageRecord]] = {}
        self._activity: dict[str, int] = {}
        self._next_activity = 0

    def snapshot(self, session_id: str) -> list[MessageRecord]:
        return list(self._messages.get(session_id, []))

    async def create_session(
        self,
        *,
        school_email: str,
        condition_id: str,
        entry_path: str,
        opening_message: str,
    ) -> SessionRecord:
        now = datetime.now(UTC)
        session = SessionRecord(
            id=str(uuid4()),
            school_email=school_email,
            condition_id=condition_id,
            entry_path=entry_path,
            created_at=now,
            updated_at=now,
        )
        self.sessions[session.id] = session
        self._messages[session.id] = []
        self._touch(session.id)
        if opening_message.strip():
            await self.append_message(
                session_id=session.id,
                school_email=school_email,
                condition_id=condition_id,
                entry_path=entry_path,
                role="assistant",
                content=opening_message.strip(),
                status="opening",
                reason="",
                layer="",
                citations=[],
            )
        return self.sessions[session.id]

    async def get_session(self, session_id: str) -> SessionRecord | None:
        return self.sessions.get(session_id)

    async def list_sessions(
        self,
        school_email: str,
        entry_path: str | None = None,
    ) -> list[SessionRecord]:
        matched = [
            session
            for session in self.sessions.values()
            if session.school_email == school_email
            and (entry_path is None or session.entry_path == entry_path)
        ]
        matched.sort(
            key=lambda session: (self._activity.get(session.id, 0), session.updated_at),
            reverse=True,
        )
        return matched

    async def list_messages(self, session_id: str) -> list[MessageRecord]:
        return list(self._messages.get(session_id, []))

    async def append_message(
        self,
        *,
        session_id: str,
        school_email: str,
        condition_id: str,
        entry_path: str,
        role: str,
        content: str,
        status: str,
        reason: str,
        layer: str,
        citations: list[dict[str, str]],
    ) -> MessageRecord:
        if session_id not in self.sessions:
            raise KeyError(session_id)
        message = MessageRecord(
            id=str(uuid4()),
            session_id=session_id,
            school_email=school_email,
            condition_id=condition_id,
            entry_path=entry_path,
            role=role,
            content=content,
            status=status,
            reason=reason,
            layer=layer,
            citations=_copy_citations(citations),
            created_at=datetime.now(UTC),
        )
        self._messages.setdefault(session_id, []).append(message)
        self._touch(session_id)
        return message

    def _touch(self, session_id: str) -> None:
        current = self.sessions[session_id]
        self._next_activity += 1
        self._activity[session_id] = self._next_activity
        self.sessions[session_id] = SessionRecord(
            id=current.id,
            school_email=current.school_email,
            condition_id=current.condition_id,
            entry_path=current.entry_path,
            created_at=current.created_at,
            updated_at=datetime.now(UTC),
        )


class PostgresConversationStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create_session(
        self,
        *,
        school_email: str,
        condition_id: str,
        entry_path: str,
        opening_message: str,
    ) -> SessionRecord:
        session_id = uuid4()
        now = datetime.now(UTC)
        async with self._pool.acquire() as connection, connection.transaction():
            await connection.execute(
                """
                    insert into rag.chat_sessions (
                      id, school_email, condition_id, entry_path
                    ) values ($1, $2, $3, $4)
                    """,
                session_id,
                school_email,
                condition_id,
                entry_path,
            )
            if opening_message.strip():
                await connection.execute(
                    """
                        insert into rag.chat_messages (
                          id, session_id, school_email, condition_id, entry_path,
                          role, content, status, reason, layer, citations
                        ) values (
                          $1, $2, $3, $4, $5,
                          'assistant', $6, 'opening', '', '', '[]'::jsonb
                        )
                        """,
                    uuid4(),
                    session_id,
                    school_email,
                    condition_id,
                    entry_path,
                    opening_message.strip(),
                )
        return SessionRecord(
            id=str(session_id),
            school_email=school_email,
            condition_id=condition_id,
            entry_path=entry_path,
            created_at=now,
            updated_at=now,
        )

    async def get_session(self, session_id: str) -> SessionRecord | None:
        key = _uuid_or_none(session_id)
        if key is None:
            return None
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select id, school_email, condition_id, entry_path, created_at, updated_at
                from rag.chat_sessions
                where id = $1
                """,
                key,
            )
        if row is None:
            return None
        return _session_from_row(row)

    async def list_messages(self, session_id: str) -> list[MessageRecord]:
        key = _uuid_or_none(session_id)
        if key is None:
            return []
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(
                """
                select
                  id, session_id, school_email, condition_id, entry_path,
                  role, content, status, reason, layer, citations, created_at
                from rag.chat_messages
                where session_id = $1
                order by seq asc
                """,
                key,
            )
        return [_message_from_row(row) for row in rows]

    async def list_sessions(
        self,
        school_email: str,
        entry_path: str | None = None,
    ) -> list[SessionRecord]:
        async with self._pool.acquire() as connection:
            if entry_path is None:
                rows = await connection.fetch(
                    """
                    select id, school_email, condition_id, entry_path, created_at, updated_at
                    from rag.chat_sessions
                    where school_email = $1
                    order by updated_at desc, created_at desc, id desc
                    """,
                    school_email,
                )
            else:
                rows = await connection.fetch(
                    """
                    select id, school_email, condition_id, entry_path, created_at, updated_at
                    from rag.chat_sessions
                    where school_email = $1 and entry_path = $2
                    order by updated_at desc, created_at desc, id desc
                    """,
                    school_email,
                    entry_path,
                )
        return [_session_from_row(row) for row in rows]

    async def append_message(
        self,
        *,
        session_id: str,
        school_email: str,
        condition_id: str,
        entry_path: str,
        role: str,
        content: str,
        status: str,
        reason: str,
        layer: str,
        citations: list[dict[str, str]],
    ) -> MessageRecord:
        key = _uuid_or_none(session_id)
        if key is None:
            raise KeyError(session_id)
        message_id = uuid4()
        now = datetime.now(UTC)
        async with self._pool.acquire() as connection, connection.transaction():
            await connection.execute(
                """
                    insert into rag.chat_messages (
                      id, session_id, school_email, condition_id, entry_path,
                      role, content, status, reason, layer, citations
                    ) values (
                      $1, $2, $3, $4, $5,
                      $6, $7, $8, $9, $10, $11::jsonb
                    )
                    """,
                message_id,
                key,
                school_email,
                condition_id,
                entry_path,
                role,
                content,
                status,
                reason,
                layer,
                json.dumps(citations),
            )
            await connection.execute(
                """
                    update rag.chat_sessions
                    set updated_at = now()
                    where id = $1
                    """,
                key,
            )
        return MessageRecord(
            id=str(message_id),
            session_id=str(key),
            school_email=school_email,
            condition_id=condition_id,
            entry_path=entry_path,
            role=role,
            content=content,
            status=status,
            reason=reason,
            layer=layer,
            citations=_copy_citations(citations),
            created_at=now,
        )


def resolve_conversation_store(request: Request) -> ConversationStore:
    pool = getattr(request.app.state, "db_pool", None)
    if pool is not None:
        return PostgresConversationStore(pool)
    store = getattr(request.app.state, "memory_store", None)
    if store is None:
        store = InMemoryConversationStore()
        request.app.state.memory_store = store
    return store


def _copy_citations(citations: list[dict[str, str]]) -> tuple[dict[str, str], ...]:
    copied: list[dict[str, str]] = []
    for item in citations:
        copied.append(
            {
                "source_id": str(item.get("source_id", "")),
                "title": str(item.get("title", "")),
                "location": str(item.get("location", "")),
            }
        )
    return tuple(copied)


def _uuid_or_none(value: str) -> UUID | None:
    try:
        return UUID(value)
    except (TypeError, ValueError):
        return None


def _as_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    raise TypeError("Expected a datetime column")


def _session_from_row(row: asyncpg.Record | dict[str, object]) -> SessionRecord:
    created_at = _as_datetime(row["created_at"])
    updated_at = created_at
    if _row_has(row, "updated_at") and row["updated_at"] is not None:
        updated_at = _as_datetime(row["updated_at"])
    return SessionRecord(
        id=str(row["id"]),
        school_email=str(row["school_email"]),
        condition_id=str(row["condition_id"]),
        entry_path=str(row["entry_path"]),
        created_at=created_at,
        updated_at=updated_at,
    )


def _row_has(row: asyncpg.Record | dict[str, object], key: str) -> bool:
    try:
        return key in row
    except TypeError:
        return False


def _message_from_row(row: asyncpg.Record | dict[str, object]) -> MessageRecord:
    return MessageRecord(
        id=str(row["id"]),
        session_id=str(row["session_id"]),
        school_email=str(row["school_email"]),
        condition_id=str(row["condition_id"]),
        entry_path=str(row["entry_path"]),
        role=str(row["role"]),
        content=str(row["content"]),
        status=str(row["status"]),
        reason=str(row["reason"]),
        layer=str(row["layer"]),
        citations=_load_citations(row["citations"]),
        created_at=_as_datetime(row["created_at"]),
    )


def _load_citations(value: object) -> tuple[dict[str, str], ...]:
    if value is None:
        return ()
    loaded: object = value
    if isinstance(value, str):
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            return ()
    if not isinstance(loaded, list):
        return ()
    items: list[dict[str, str]] = []
    for item in loaded:
        if isinstance(item, dict):
            items.append(
                {
                    "source_id": str(item.get("source_id", "")),
                    "title": str(item.get("title", "")),
                    "location": str(item.get("location", "")),
                }
            )
    return tuple(items)
