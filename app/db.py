from __future__ import annotations

import ssl
from pathlib import Path

import asyncpg
import certifi

# Persistent Coolify/Docker containers should use Supavisor session mode (port 5432).
# statement_cache_size=0 also works with transaction mode (port 6543).
POOL_MIN_SIZE = 1
POOL_MAX_SIZE = 5
_POOLER_CA = Path(__file__).resolve().parent / "certs" / "supabase-pooler-ca.crt"


def _ssl_context() -> ssl.SSLContext:
    cafile = str(_POOLER_CA) if _POOLER_CA.is_file() else certifi.where()
    return ssl.create_default_context(cafile=cafile)


def to_asyncpg_dsn(url: str) -> str:
    cleaned = url.strip()
    if cleaned.startswith("postgresql+asyncpg://"):
        return "postgresql://" + cleaned.removeprefix("postgresql+asyncpg://")
    if cleaned.startswith("postgres://"):
        return "postgresql://" + cleaned.removeprefix("postgres://")
    if cleaned.startswith("postgresql://"):
        return cleaned
    return ""


async def create_pool(database_url: str) -> asyncpg.Pool | None:
    dsn = to_asyncpg_dsn(database_url)
    if not dsn:
        return None
    ssl_context = _ssl_context()
    return await asyncpg.create_pool(
        dsn=dsn,
        min_size=POOL_MIN_SIZE,
        max_size=POOL_MAX_SIZE,
        ssl=ssl_context,
        statement_cache_size=0,
        command_timeout=15,
        timeout=20,
    )


async def ping_db(pool: asyncpg.Pool) -> bool:
    async with pool.acquire() as connection:
        return await connection.fetchval("select 1") == 1


async def close_pool(pool: asyncpg.Pool | None) -> None:
    if pool is not None:
        await pool.close()
