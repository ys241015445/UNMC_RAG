from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "UNMC 课程助手"
    school_email_domain: str = "unmc.edu"
    course_terms: str = "高等数学,微积分,线性代数"
    minimum_retrieval_score: float = 0.75
    # 指向 documents.jsonl 时启用本地关键词检索原型；空则 EmptyRetriever。
    corpus_path: str = ""
    chunk_size: int = 500
    chunk_overlap: int = 80
    retrieval_top_k: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="UNMC_RAG_",
        extra="ignore",
    )

    @property
    def course_term_set(self) -> set[str]:
        return {term.strip() for term in self.course_terms.split(",") if term.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
