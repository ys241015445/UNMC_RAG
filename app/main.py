from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from logging import getLogger
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import create_api_router
from app.auth.policy import SchoolEmailPolicy
from app.config import (
    get_database_settings,
    get_probe_settings,
    get_settings,
    get_smtp_settings,
)
from app.db import close_pool, create_pool, ping_db
from app.healthcheck.loop import start_background_probe, stop_background_probe
from app.rag.factory import build_chat_service
from app.web.ui import create_ui_router

logger = getLogger(__name__)

settings = get_settings()
chat_service = build_chat_service(settings)

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    pool = None
    db_settings = get_database_settings()
    if db_settings.enabled:
        try:
            pool = await create_pool(db_settings.database_url)
        except Exception:
            logger.exception("Failed to connect to Supabase Postgres")
            pool = None
    app.state.db_pool = pool
    start_background_probe(
        app,
        chat_service=chat_service,
        probe_settings=get_probe_settings(),
        smtp_settings=get_smtp_settings(),
    )
    try:
        yield
    finally:
        await stop_background_probe(app)
        await close_pool(getattr(app.state, "db_pool", None))


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Answers only questions supported by on-campus course evidence.",
    lifespan=lifespan,
)
app.include_router(
    create_ui_router(
        app_name=settings.app_name,
        school_email_domain=settings.school_email_domain,
    )
)
app.include_router(
    create_api_router(
        chat_service=chat_service,
        school_email_policy=SchoolEmailPolicy(settings.school_email_domain),
    )
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "unmc-rag"}


@app.get("/ready")
async def ready(request: Request) -> JSONResponse:
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        payload = {"status": "ok", "service": "unmc-rag", "database": "disabled"}
        return JSONResponse(payload, status_code=200)
    try:
        ok = await ping_db(pool)
    except Exception:
        return JSONResponse(
            {"status": "degraded", "service": "unmc-rag", "database": "down"},
            status_code=503,
        )
    if not ok:
        return JSONResponse(
            {"status": "degraded", "service": "unmc-rag", "database": "down"},
            status_code=503,
        )
    return JSONResponse(
        {"status": "ok", "service": "unmc-rag", "database": "up"},
        status_code=200,
    )
