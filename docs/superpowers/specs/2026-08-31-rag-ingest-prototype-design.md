# Local Corpus RAG Ingest Prototype

**日期:** 2026-08-31  
**分支:** `feat/rag-ingest-prototype`

## Goal

Load scraped `documents.jsonl` into an in-process keyword retriever and answer via existing `/api/v1/chat` without embeddings or pgvector.

## Design

- `app/ingestion/loaders.py` — JSONL → `LoadedDocument`
- `app/ingestion/chunking.py` — fixed-size character chunks
- `app/rag/retrievers.py` — `LocalKeywordRetriever` (token overlap score)
- `app/rag/factory.py` — choose Empty vs Local based on `UNMC_RAG_CORPUS_PATH`
- Guardrails still require `UNMC_RAG_COURSE_TERMS` hit

## Non-goals

- Embedding API / pgvector
- PDF download
- LLM answer rewriting (still returns concatenated evidence chunks)
