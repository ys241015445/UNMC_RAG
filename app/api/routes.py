from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.policy import SchoolEmailPolicy
from app.rag.service import ChatService


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)


class CitationResponse(BaseModel):
    source_id: str
    title: str
    location: str


class ChatResponse(BaseModel):
    status: str
    reason: str
    layer: str
    answer: str
    citations: list[CitationResponse]


def create_api_router(
    chat_service: ChatService,
    school_email_policy: SchoolEmailPolicy,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.post("/chat", response_model=ChatResponse)
    def chat(
        payload: ChatRequest,
        school_email: Annotated[str | None, Header(alias="X-School-Email")] = None,
    ) -> ChatResponse:
        try:
            school_email_policy.normalize_and_validate(school_email or "")
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="A valid school email identity is required in this prototype",
            ) from error

        result = chat_service.answer(payload.question)
        return ChatResponse(
            status=result.status,
            reason=result.reason,
            layer=result.layer,
            answer=result.answer,
            citations=[
                CitationResponse(
                    source_id=citation.source_id,
                    title=citation.title,
                    location=citation.location,
                )
                for citation in result.citations
            ],
        )

    return router
