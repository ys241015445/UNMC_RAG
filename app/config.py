from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "UNMC Course Assistant"
    school_email_domain: str = "unmc.edu"
    course_terms: str = (
        "calculus,linear algebra,graduation,shuttle,counselling,"
        "timetable,appeals,examination,visa,wellbeing,amenities,"
        "quality manual,academic regulations,assessment,admissions,complaints"
    )
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
    """Loads LLM_* from .env (Zhipu OpenAI-compatible API)."""

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


class DatabaseSettings(BaseSettings):
    """Loads DATABASE_URL (Supabase Postgres pooler or direct)."""

    database_url: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @property
    def enabled(self) -> bool:
        url = self.database_url.strip().lower()
        return url.startswith(("postgres://", "postgresql://", "postgresql+asyncpg://"))


class SmtpSettings(BaseSettings):
    """Loads SMTP_* from .env for failure notification mail."""

    host: str = ""
    port: int = 587
    username: str = ""
    password: str = ""
    from_address: str = ""
    to_address: str = "yellow.sea@live.cn"
    use_tls: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SMTP_",
        extra="ignore",
    )

    @property
    def enabled(self) -> bool:
        return bool(self.host.strip() and self.to_address.strip())

    @property
    def sender(self) -> str:
        return self.from_address.strip() or self.username.strip() or self.to_address.strip()


class ProbeSettings(BaseSettings):
    """Synthetic query loop: UNMC_RAG_PROBE_*."""

    enabled: bool = True
    interval_hours: float = 96
    startup_delay_seconds: float = 120
    question: str = "When is the next graduation ceremony?"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="UNMC_RAG_PROBE_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_llm_settings() -> LLMSettings:
    return LLMSettings()


@lru_cache
def get_database_settings() -> DatabaseSettings:
    return DatabaseSettings()


@lru_cache
def get_smtp_settings() -> SmtpSettings:
    return SmtpSettings()


@lru_cache
def get_probe_settings() -> ProbeSettings:
    return ProbeSettings()
