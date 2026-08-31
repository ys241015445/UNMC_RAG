"""将长文本切成适合检索的片段。"""

from __future__ import annotations


def chunk_text(text: str, *, chunk_size: int = 500, overlap: int = 80) -> list[str]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be in [0, chunk_size)")

    chunks: list[str] = []
    start = 0
    length = len(cleaned)
    while start < length:
        end = min(start + chunk_size, length)
        piece = cleaned[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= length:
            break
        start = end - overlap
    return chunks
