from app.db import to_asyncpg_dsn


def test_to_asyncpg_dsn_strips_sqlalchemy_prefix() -> None:
    assert (
        to_asyncpg_dsn("postgresql+asyncpg://postgres.abc:secret@host:5432/postgres")
        == "postgresql://postgres.abc:secret@host:5432/postgres"
    )


def test_to_asyncpg_dsn_normalizes_postgres_scheme() -> None:
    assert to_asyncpg_dsn("postgres://user:pass@host/db") == "postgresql://user:pass@host/db"


def test_to_asyncpg_dsn_blank() -> None:
    assert to_asyncpg_dsn("  ") == ""


def test_to_asyncpg_dsn_rejects_https_dashboard_url() -> None:
    assert to_asyncpg_dsn("https://supabase.com/dashboard/project/abc") == ""
