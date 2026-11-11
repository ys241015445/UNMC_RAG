from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.auth.policy import SchoolEmailPolicy
from app.rag.conversation_store import ConversationStore, InMemoryChatHistory


class SaveConversationRequest(BaseModel):
    title: str = Field(default="", max_length=120)
    messages: list[dict[str, Any]] = Field(default_factory=list, max_length=200)


def create_conversations_router(school_email_policy: SchoolEmailPolicy) -> APIRouter:
    router = APIRouter(prefix="/api/v1/conversations")

    def current_email(school_email: str | None) -> str:
        try:
            return school_email_policy.normalize_and_validate(school_email or "")
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="A valid school email identity is required in this prototype",
            ) from error

    def store_for(request: Request) -> ConversationStore | InMemoryChatHistory:
        pool = getattr(request.app.state, "db_pool", None)
        if pool is not None:
            return ConversationStore(pool)
        store = getattr(request.app.state, "chat_history_store", None)
        if store is None:
            store = InMemoryChatHistory()
            request.app.state.chat_history_store = store
        return store

    @router.get("")
    async def list_conversations(
        request: Request,
        school_email: Annotated[str | None, Header(alias="X-School-Email")] = None,
    ) -> dict[str, Any]:
        email = current_email(school_email)
        store = store_for(request)
        conversations = await store.list_conversations(email)
        return {"conversations": conversations}

    @router.get("/{conversation_id}")
    async def load_conversation(
        conversation_id: str,
        request: Request,
        school_email: Annotated[str | None, Header(alias="X-School-Email")] = None,
    ) -> dict[str, Any]:
        email = current_email(school_email)
        store = store_for(request)
        conversation = await store.load_conversation(email, conversation_id)
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
        return conversation

    @router.put("/{conversation_id}")
    async def save_conversation(
        conversation_id: str,
        payload: SaveConversationRequest,
        request: Request,
        school_email: Annotated[str | None, Header(alias="X-School-Email")] = None,
    ) -> dict[str, Any]:
        email = current_email(school_email)
        store = store_for(request)
        await store.save_conversation(email, conversation_id, payload.title, payload.messages)
        return {"status": "saved", "id": conversation_id}

    return router
