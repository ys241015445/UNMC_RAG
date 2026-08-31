from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import create_api_router
from app.auth.policy import SchoolEmailPolicy
from app.config import get_settings
from app.rag.factory import build_chat_service
from app.web.ui import create_ui_router

settings = get_settings()
chat_service = build_chat_service(settings)

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Answers only questions supported by on-campus course evidence.",
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
