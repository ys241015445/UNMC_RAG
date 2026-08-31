from pathlib import Path

from app.config import LLMSettings, Settings, get_llm_settings, get_settings
from app.guardrails.policy import GuardrailPolicy
from app.llm.client import OpenAICompatibleChatClient
from app.llm.generator import EvidenceAnswerGenerator
from app.rag.contracts import Retriever
from app.rag.retrievers import EmptyRetriever, LocalKeywordRetriever
from app.rag.service import AnswerGenerator, ChatService


def build_retriever(settings: Settings | None = None) -> Retriever:
    """按配置构建检索器；未配置或语料缺失时回退到空检索。"""
    resolved = settings or get_settings()
    corpus = resolved.corpus_path.strip()
    if not corpus:
        return EmptyRetriever()

    path = Path(corpus)
    if not path.is_file():
        return EmptyRetriever()

    return LocalKeywordRetriever.from_documents_jsonl(
        path,
        chunk_size=resolved.chunk_size,
        overlap=resolved.chunk_overlap,
        top_k=resolved.retrieval_top_k,
    )


def build_generator(llm_settings: LLMSettings | None = None) -> AnswerGenerator | None:
    resolved = llm_settings or get_llm_settings()
    if not resolved.enabled:
        return None
    client = OpenAICompatibleChatClient(
        api_base=resolved.api_base,
        api_key=resolved.api_key,
        model=resolved.model,
    )
    return EvidenceAnswerGenerator(client)


def build_chat_service(
    settings: Settings | None = None,
    llm_settings: LLMSettings | None = None,
) -> ChatService:
    resolved = settings or get_settings()
    return ChatService(
        guardrails=GuardrailPolicy(course_terms=resolved.course_term_set),
        retriever=build_retriever(resolved),
        minimum_score=resolved.minimum_retrieval_score,
        generator=build_generator(llm_settings),
    )
