"""Multi-turn study chat. Condition ids stay on the server."""

import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field, model_validator

from app.auth.policy import SchoolEmailPolicy
from app.conversations.store import (
    ConversationStore,
    MessageRecord,
    SessionRecord,
    resolve_conversation_store,
)
from app.experiment.catalog import ExperimentCondition, get_condition_catalog
from app.rag.contracts import DialogueTurn
from app.rag.service import ChatService


class ExperimentCitation(BaseModel):
    source_id: str
    title: str
    location: str


class ExperimentChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2_000)
    session_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def accept_question_alias(cls, data: object) -> object:
        if isinstance(data, dict) and not str(data.get("message") or "").strip():
            question = data.get("question")
            if isinstance(question, str) and question.strip():
                return {**data, "message": question}
        return data


class ExperimentChatResponse(BaseModel):
    session_id: str
    status: str
    reason: str
    layer: str
    answer: str
    citations: list[ExperimentCitation]


class TranscriptMessage(BaseModel):
    role: str
    content: str
    citations: list[ExperimentCitation]


class TranscriptResponse(BaseModel):
    session_id: str
    messages: list[TranscriptMessage]


def clip_dialogue(history: list[DialogueTurn], limit: int) -> list[DialogueTurn]:
    if limit <= 0:
        return []
    return list(history[-limit:])


def create_experiment_router(
    chat_service: ChatService,
    school_email_policy: SchoolEmailPolicy,
) -> APIRouter:
    router = APIRouter()

    @router.post("/chat/{entry_path}/messages", response_model=ExperimentChatResponse)
    async def post_message(
        entry_path: str,
        payload: ExperimentChatRequest,
        request: Request,
        school_email: Annotated[str | None, Header(alias="X-School-Email")] = None,
    ) -> ExperimentChatResponse:
        condition = _require_condition(entry_path)
        email = _require_email(school_email_policy, school_email)
        store = resolve_conversation_store(request)
        session = await _session_for_turn(
            store,
            session_id=payload.session_id,
            email=email,
            condition=condition,
        )
        prior = await store.list_messages(session.id)
        history = clip_dialogue(_history_from(prior), _history_limit())

        await store.append_message(
            session_id=session.id,
            school_email=email,
            condition_id=condition.condition_id,
            entry_path=condition.entry_path,
            role="user",
            content=payload.message,
            status="received",
            reason="",
            layer="",
            citations=[],
        )

        result = await asyncio.to_thread(
            chat_service.answer_in_context,
            payload.message,
            history=history,
            system_prompt=condition.system_prompt,
            temperature=condition.temperature,
            max_tokens=condition.max_tokens,
        )
        citations = [
            {
                "source_id": citation.source_id,
                "title": citation.title,
                "location": citation.location,
            }
            for citation in result.citations
        ]
        answer = result.answer.strip() or condition.refusal_text(result.reason)
        await store.append_message(
            session_id=session.id,
            school_email=email,
            condition_id=condition.condition_id,
            entry_path=condition.entry_path,
            role="assistant",
            content=answer,
            status=result.status,
            reason=result.reason,
            layer=result.layer,
            citations=citations,
        )
        return ExperimentChatResponse(
            session_id=session.id,
            status=result.status,
            reason=result.reason,
            layer=result.layer,
            answer=answer,
            citations=[ExperimentCitation(**item) for item in citations],
        )

    @router.get(
        "/chat/{entry_path}/sessions/{session_id}",
        response_model=TranscriptResponse,
    )
    async def get_transcript(
        entry_path: str,
        session_id: str,
        request: Request,
        school_email: Annotated[str | None, Header(alias="X-School-Email")] = None,
    ) -> TranscriptResponse:
        condition = _require_condition(entry_path)
        email = _require_email(school_email_policy, school_email)
        store = resolve_conversation_store(request)
        session = await store.get_session(_canonical_session_id(session_id))
        if (
            session is None
            or session.school_email != email
            or session.entry_path != condition.entry_path
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
        messages = await store.list_messages(session.id)
        return TranscriptResponse(
            session_id=session.id,
            messages=[_public_message(message) for message in messages],
        )

    return router


def _history_limit() -> int:
    from app.config import get_settings

    return get_settings().experiment_history_messages


def _require_condition(entry_path: str) -> ExperimentCondition:
    condition = get_condition_catalog().get(entry_path)
    if condition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return condition


def _require_email(policy: SchoolEmailPolicy, school_email: str | None) -> str:
    try:
        return policy.normalize_and_validate(school_email or "")
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid school email identity is required in this prototype",
        ) from error


async def _session_for_turn(
    store: ConversationStore,
    *,
    session_id: str | None,
    email: str,
    condition: ExperimentCondition,
) -> SessionRecord:
    if session_id is None or not session_id.strip():
        return await store.create_session(
            school_email=email,
            condition_id=condition.condition_id,
            entry_path=condition.entry_path,
            opening_message=condition.opening_message,
        )
    canonical = _canonical_session_id(session_id)
    session = await store.get_session(canonical)
    mismatched = (
        session is None
        or session.school_email != email
        or session.entry_path != condition.entry_path
    )
    if mismatched:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return session


def _canonical_session_id(session_id: str) -> str:
    try:
        return str(UUID(session_id.strip()))
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session id",
        ) from error


def _history_from(messages: list[MessageRecord]) -> list[DialogueTurn]:
    history: list[DialogueTurn] = []
    for message in messages:
        if message.role in {"user", "assistant"} and message.content.strip():
            history.append(DialogueTurn(role=message.role, content=message.content))
    return history


def _public_message(message: MessageRecord) -> TranscriptMessage:
    return TranscriptMessage(
        role=message.role,
        content=message.content,
        citations=[ExperimentCitation(**item) for item in message.citations],
    )
