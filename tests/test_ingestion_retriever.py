from pathlib import Path

from app.config import Settings
from app.ingestion.chunking import chunk_text
from app.ingestion.loaders import LoadedDocument, load_documents_jsonl
from app.rag.factory import build_retriever
from app.rag.retrievers import EmptyRetriever, LocalKeywordRetriever, search_terms, tokenize


def test_chunk_text_respects_size_and_overlap() -> None:
    text = "a" * 1200
    chunks = chunk_text(text, chunk_size=500, overlap=100)
    assert len(chunks) >= 3
    assert all(len(chunk) <= 500 for chunk in chunks)


def test_load_documents_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "documents.jsonl"
    path.write_text(
        (
            '{"id":"d1","title":"Graduation","url":"https://example.edu/g",'
            '"text":"Ceremony in January."}\n'
        ),
        encoding="utf-8",
    )
    docs = load_documents_jsonl(path)
    assert len(docs) == 1
    assert docs[0].source_id == "d1"
    assert "Ceremony" in docs[0].text


def test_tokenize_english_and_cjk() -> None:
    assert tokenize("Shuttle Bus") == ["shuttle", "bus"]
    # Keep a CJK sample to verify Unicode tokenization still works.
    chinese = tokenize("高等数学考试")
    assert "高" in chinese
    assert "学" in chinese
    assert "高等数学考试" in chinese


def test_search_terms_expand_graduate_variants() -> None:
    terms = search_terms("the next graduate time")
    assert "graduation" in terms or "graduate" in terms
    assert "the" not in terms
    assert "next" not in terms
    typo_terms = search_terms("when is next graducation time")
    assert "graduation" in typo_terms


def test_local_keyword_retriever_matches_graduate_to_graduation() -> None:
    retriever = LocalKeywordRetriever.from_documents(
        [
            LoadedDocument(
                source_id="grad-1",
                title="Graduation Ceremony",
                url="https://example.edu/grad",
                text="The upcoming graduation is planned for 30 January 2027 - 31 January 2027.",
            )
        ],
        chunk_size=300,
        overlap=20,
        top_k=3,
    )
    hits = retriever.search("the next graduate time")
    assert hits
    assert hits[0].source_id == "grad-1"
    assert hits[0].score >= 0.3


def test_local_keyword_retriever_from_memory_docs() -> None:
    retriever = LocalKeywordRetriever.from_documents(
        [
            LoadedDocument(
                source_id="shuttle-1",
                title="Shuttle Bus",
                url="https://example.edu/shuttle",
                text=(
                    "Shuttle Bus and Transport Services provide campus routes for students. "
                    "Check the shuttle bus timetable for Semenyih campus."
                ),
            ),
            LoadedDocument(
                source_id="food-1",
                title="Amenities",
                url="https://example.edu/food",
                text="Food and beverage outlets open on weekdays near the lake.",
            ),
        ],
        chunk_size=200,
        overlap=20,
        top_k=3,
    )

    hits = retriever.search("shuttle bus timetable")
    assert hits
    assert hits[0].source_id == "shuttle-1"
    assert hits[0].score >= 0.5
    assert "shuttle" in hits[0].text.casefold()


def test_build_retriever_falls_back_when_corpus_missing(tmp_path: Path) -> None:
    settings = Settings(corpus_path=str(tmp_path / "missing.jsonl"))
    assert isinstance(build_retriever(settings), EmptyRetriever)


def test_build_retriever_loads_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "documents.jsonl"
    path.write_text(
        '{"id":"g1","title":"Graduation","url":"https://example.edu/g",'
        '"text":"Graduation ceremonies are held twice a year on campus."}\n',
        encoding="utf-8",
    )
    settings = Settings(corpus_path=str(path), chunk_size=200, chunk_overlap=20)
    retriever = build_retriever(settings)
    assert isinstance(retriever, LocalKeywordRetriever)
    hits = retriever.search("graduation ceremonies campus")
    assert hits
    assert hits[0].source_id == "g1"


def test_build_retriever_loads_comma_separated_corpora(tmp_path: Path) -> None:
    first = tmp_path / "current.jsonl"
    second = tmp_path / "quality.jsonl"
    first.write_text(
        '{"id":"g1","title":"Graduation","url":"https://example.edu/g",'
        '"text":"Graduation ceremonies are held twice a year on campus."}\n',
        encoding="utf-8",
    )
    second.write_text(
        '{"id":"q1","title":"Quality Manual","url":"https://example.edu/q",'
        '"text":"The Quality Manual sets academic regulations for assessment."}\n',
        encoding="utf-8",
    )
    settings = Settings(
        corpus_path=f"{first},{second}",
        chunk_size=200,
        chunk_overlap=20,
    )
    retriever = build_retriever(settings)
    hits = retriever.search("quality manual academic regulations assessment")
    assert hits
    assert hits[0].source_id == "q1"
