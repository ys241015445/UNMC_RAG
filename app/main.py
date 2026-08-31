from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import create_api_router
from app.auth.policy import SchoolEmailPolicy
from app.config import get_settings
from app.guardrails.policy import GuardrailPolicy
from app.rag.factory import build_retriever
from app.rag.service import ChatService
from app.web.ui import create_ui_router

settings = get_settings()
chat_service = ChatService(
    guardrails=GuardrailPolicy(course_terms=settings.course_term_set),
    retriever=build_retriever(settings),
    minimum_score=settings.minimum_retrieval_score,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="仅回答有校内课程资料证据支持的问题。",
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
