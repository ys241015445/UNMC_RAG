from pathlib import Path

from app.config import LLMSettings, Settings, get_llm_settings, get_settings
from app.guardrails.policy import GuardrailPolicy
from app.guardrails.topic_classifier import LLMTopicClassifier
from app.ingestion.loaders import load_documents_jsonl
from app.llm.client import OpenAICompatibleChatClient
from app.llm.generator import EvidenceAnswerGenerator
from app.rag.contracts import Retriever
from app.rag.query_rewrite import QueryRewriter
from app.rag.retrievers import EmptyRetriever, LocalKeywordRetriever
from app.rag.service import AnswerGenerator, ChatService


def corpus_paths(corpus: str) -> list[Path]:
    return [Path(part.strip()) for part in corpus.split(",") if part.strip()]


def build_retriever(settings: Settings | None = None) -> Retriever:
    """Build a retriever from one or more JSONL corpora; empty if none exist."""
    resolved = settings or get_settings()
    paths = [path for path in corpus_paths(resolved.corpus_path) if path.is_file()]
    if not paths:
        return EmptyRetriever()

    documents = []
    for path in paths:
        documents.extend(load_documents_jsonl(path))
    if not documents:
        return EmptyRetriever()

    return LocalKeywordRetriever.from_documents(
        documents,
        chunk_size=resolved.chunk_size,
        overlap=resolved.chunk_overlap,
        top_k=resolved.retrieval_top_k,
    )


def _build_llm_client(llm_settings: LLMSettings) -> OpenAICompatibleChatClient | None:
    if not llm_settings.enabled:
        return None
    return OpenAICompatibleChatClient(
        api_base=llm_settings.api_base,
        api_key=llm_settings.api_key,
        model=llm_settings.model,
    )


def build_generator(
    llm_settings: LLMSettings | None = None,
    *,
    client: OpenAICompatibleChatClient | None = None,
) -> AnswerGenerator | None:
    resolved = llm_settings or get_llm_settings()
    llm_client = client if client is not None else _build_llm_client(resolved)
    if llm_client is None:
        return None
    return EvidenceAnswerGenerator(llm_client)


def build_query_rewriter(
    llm_settings: LLMSettings | None = None,
    *,
    client: OpenAICompatibleChatClient | None = None,
) -> QueryRewriter | None:
    resolved = llm_settings or get_llm_settings()
    llm_client = client if client is not None else _build_llm_client(resolved)
    if llm_client is None:
        return None
    return QueryRewriter(llm_client)


def build_guardrails(
    settings: Settings | None = None,
    llm_settings: LLMSettings | None = None,
    *,
    client: OpenAICompatibleChatClient | None = None,
) -> GuardrailPolicy:
    resolved = settings or get_settings()
    resolved_llm = llm_settings or get_llm_settings()
    llm_client = client if client is not None else _build_llm_client(resolved_llm)
    classifier = None
    if llm_client is not None:
        classifier = LLMTopicClassifier(
            llm_client,
            topic_hints=resolved.course_term_set,
        )
    return GuardrailPolicy(
        course_terms=resolved.course_term_set,
        topic_classifier=classifier,
    )


def build_chat_service(
    settings: Settings | None = None,
    llm_settings: LLMSettings | None = None,
) -> ChatService:
    resolved = settings or get_settings()
    resolved_llm = llm_settings or get_llm_settings()
    client = _build_llm_client(resolved_llm)
    return ChatService(
        guardrails=build_guardrails(resolved, resolved_llm, client=client),
        retriever=build_retriever(resolved),
        minimum_score=resolved.minimum_retrieval_score,
        generator=build_generator(resolved_llm, client=client),
        query_rewriter=build_query_rewriter(resolved_llm, client=client),
    )
