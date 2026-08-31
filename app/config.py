from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "UNMC 课程助手"
    school_email_domain: str = "unmc.edu"
    course_terms: str = "高等数学,微积分,线性代数"
    minimum_retrieval_score: float = 0.75
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


class LLMSettings(BaseSettings):
    """读取 .env 中的 LLM_*（智谱 OpenAI 兼容）。"""

    api_base: str = "https://open.bigmodel.cn/api/paas/v4/"
    api_key: str = ""
    model: str = "glm-4.5-air"
    embedding_model: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="LLM_",
        extra="ignore",
    )

    @property
    def enabled(self) -> bool:
        return bool(self.api_key.strip() and self.model.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_llm_settings() -> LLMSettings:
    return LLMSettings()
