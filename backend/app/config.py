"""Application settings, loaded from environment variables and backend/.env.

Every tunable value lives here (CLAUDE.md rule). Add settings on the day they are needed.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # "production" disables dev-only shortcuts such as creating tables at startup.
    environment: Literal["development", "test", "production"] = "development"

    # LLM (SPEC section 6). "none" = no LLM: chat degrades to returning passages.
    llm_provider: Literal["groq", "gemini", "none"] = "none"
    # SecretStr: printed as '**********' in logs, reprs and error messages.
    groq_api_key: SecretStr | None = None
    groq_model: str | None = None
    gemini_api_key: SecretStr | None = None
    gemini_model: str | None = None
    llm_timeout_seconds: float = 20.0
    llm_max_retries: int = 3  # retries after the first attempt, for 429 / 5xx / network errors
    llm_backoff_base_seconds: float = 1.0  # waits 1 s, 2 s, 4 s
    llm_max_retry_after_seconds: float = 20.0  # cap on a server-sent Retry-After

    # RAG (SPEC section 6).
    retrieval_top_k: int = 5
    # PROVISIONAL until measured on Day 3 (docs/EXPERIMENTS.md). Below this: no LLM call.
    low_confidence_threshold: float = 0.35
    low_confidence_passages: int = 2
    chat_temperature: float = 0.2
    chat_max_tokens: int = 600
    citation_excerpt_chars: int = 320
    fallback_passage_chars: int = 400

    # Database: SQLite locally, Postgres in production.
    database_url: str = "sqlite:///./data/quorix.db"

    # Service-to-service token (SPEC section 2). Required, no default, at least 32 chars.
    backend_jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "quorix-web"
    jwt_audience: str = "quorix-api"
    # Tolerated clock difference between the Next.js and FastAPI hosts when checking exp/iat.
    jwt_leeway_seconds: int = 5
    org_id_pattern: str = r"^[a-zA-Z0-9_-]{1,64}$"

    # Input limits (validated by app/schemas.py).
    max_question_chars: int = 2000

    # Crawler (SPEC section 5.1).
    crawl_max_pages: int = 120
    crawl_max_depth: int = 3
    crawl_delay_seconds: float = 0.4
    crawl_timeout_seconds: float = 10.0
    crawl_max_redirects: int = 5
    crawl_max_page_bytes: int = 5 * 1024 * 1024
    crawl_user_agent: str = "Quorix/1.0 (+https://github.com/thakur-pranav/Quorix)"
    # Only follow links under the start page's path ("/en/billing" -> "/en/billing/..."),
    # not the whole domain. Stricter than SPEC 5.1's "same site"; see docs/NOTES.md Day 3.
    crawl_stay_in_section: bool = True

    # Chunker (SPEC section 5.4).
    chunk_max_words: int = 220
    chunk_overlap_words: int = 40
    chunk_min_words: int = 15
    chunk_merge_below_words: int = 110
    # Drop text blocks where more than this share of the words are link text (menus, link lists).
    chunk_max_link_density: float = 0.6

    # Embeddings and vector store (SPEC sections 5.5 and 5.6).
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_batch_size: int = 64
    chroma_path: str = "./data/chroma"  # ":memory:" = in-process, nothing on disk (tests)
    chroma_collection: str = "chunks"

    # Uploads (SPEC section 4).
    upload_dir: str = "./data/uploads"
    upload_max_bytes: int = 10 * 1024 * 1024
    upload_allowed_extensions: tuple[str, ...] = (".pdf", ".docx", ".txt", ".md")

    # Comma-separated list of browser origins allowed by CORS.
    cors_origins: str = "http://localhost:3000"

    @model_validator(mode="after")
    def _llm_provider_is_configured(self) -> Settings:
        """Fail at startup if the chosen LLM provider has no key or model."""
        required = {
            "groq": (self.groq_api_key, self.groq_model),
            "gemini": (self.gemini_api_key, self.gemini_model),
        }.get(self.llm_provider)
        if required is not None and not all(required):
            name = self.llm_provider.upper()
            raise ValueError(f"LLM_PROVIDER={self.llm_provider} needs {name}_API_KEY and {name}_MODEL")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
