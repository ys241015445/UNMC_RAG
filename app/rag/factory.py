from pathlib import Path

from app.config import Settings, get_settings
from app.rag.contracts import Retriever
from app.rag.retrievers import EmptyRetriever, LocalKeywordRetriever


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
