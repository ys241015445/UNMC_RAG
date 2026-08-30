from app.rag.contracts import RetrievedChunk


class EmptyRetriever:
    """占位检索器；接入 pgvector 前安全地返回无证据。"""

    def search(self, question: str) -> list[RetrievedChunk]:
        return []
