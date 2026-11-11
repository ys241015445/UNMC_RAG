import asyncio
from datetime import UTC, datetime

from app.conversations.store import PostgresConversationStore
from app.privacy.crypto import AesFieldCipher

CIPHER = AesFieldCipher(bytes(range(32)))


class _Context:
    def __init__(self, value: object | None = None) -> None:
        self.value = value

    async def __aenter__(self) -> object | None:
        return self.value

    async def __aexit__(self, *exc: object) -> bool:
        return False


class FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, str, tuple[object, ...]]] = []

    def transaction(self) -> _Context:
        return _Context(None)

    async def execute(self, query: str, *args: object) -> str:
        self.executed.append(("execute", " ".join(query.split()), args))
        return "OK"

    async def fetch(self, query: str, *args: object) -> list[dict[str, object]]:
        self.executed.append(("fetch", " ".join(query.split()), args))
        return [
            {
                "id": args[0] if False else "11111111-1111-1111-1111-111111111111",
                "session_id": args[0],
                "school_email": "student@unmc.edu",
                "condition_id": "HH",
                "entry_path": "t5w1",
                "role": "user",
                "content": "When is graduation?",
                "status": "received",
                "reason": "",
                "layer": "",
                "citations": '[{"source_id": "grad-1", "title": "Graduation", "location": "p1"}]',
                "created_at": datetime(2026, 11, 4, tzinfo=UTC),
            }
        ]

    async def fetchrow(self, query: str, *args: object) -> dict[str, object]:
        self.executed.append(("fetchrow", " ".join(query.split()), args))
        return {
            "id": args[0],
            "school_email": "student@unmc.edu",
            "condition_id": "HH",
            "entry_path": "t5w1",
            "created_at": datetime(2026, 11, 4, tzinfo=UTC),
        }


class FakePool:
    def __init__(self) -> None:
        self.conn = FakeConnection()

    def acquire(self) -> _Context:
        return _Context(self.conn)


def test_postgres_list_sessions_filters_email_and_path_newest_first() -> None:
    async def scenario() -> None:
        pool = FakePool()
        store = PostgresConversationStore(pool, cipher=CIPHER)  # type: ignore[arg-type]
        await store.list_sessions("ada@unmc.edu", "k7q2")
        kind, sql, args = pool.conn.executed[-1]
        assert kind == "fetch"
        assert "from rag.chat_sessions" in sql
        assert "school_email_hash = $1" in sql
        assert "entry_path = $2" in sql
        assert "order by updated_at desc" in sql
        assert args == (CIPHER.email_index("ada@unmc.edu"), "k7q2")

    asyncio.run(scenario())


def test_postgres_writes_include_email_condition_and_path() -> None:
    async def scenario() -> None:
        pool = FakePool()
        store = PostgresConversationStore(pool, cipher=CIPHER)  # type: ignore[arg-type]
        session = await store.create_session(
            school_email="student@unmc.edu",
            condition_id="LH",
            entry_path="m3x9",
            opening_message="Hi, I am glad you are here.",
        )
        await store.append_message(
            session_id=session.id,
            school_email="student@unmc.edu",
            condition_id="LH",
            entry_path="m3x9",
            role="user",
            content="When is graduation?",
            status="received",
            reason="",
            layer="",
            citations=[],
        )
        loaded = await store.get_session(session.id)
        messages = await store.list_messages(session.id)

        flat: list[object] = []
        statements: list[str] = []
        for _kind, sql, args in pool.conn.executed:
            statements.append(sql)
            flat.extend(args)

        assert any("insert into rag.chat_sessions" in sql for sql in statements)
        assert any("insert into rag.chat_messages" in sql for sql in statements)
        assert "student@unmc.edu" not in flat
        assert "When is graduation?" not in flat
        assert any(isinstance(value, str) and value.startswith("v1:") for value in flat)
        assert "LH" in flat
        assert "m3x9" in flat
        assert loaded is not None
        assert loaded.school_email == "student@unmc.edu"
        assert loaded.condition_id == "HH"
        assert messages[0].condition_id == "HH"
        assert messages[0].school_email == "student@unmc.edu"
        assert messages[0].citations[0]["source_id"] == "grad-1"

    asyncio.run(scenario())
