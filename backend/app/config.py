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
    # Client-side rate limit: minimum gap between requests from this process. Groq's free tier
    # allows ~30 requests/minute, so 2 s stays under it instead of hitting 429s and retrying.
    # 0 disables it (tests). Per process: several workers would need a shared limiter (Redis).
    llm_min_interval_seconds: float = 2.0

    # RAG (SPEC section 6).
    retrieval_top_k: int = 5
    # Below this: no LLM call. Day 3 measured 0.51 on 30 clean hand-written questions; Day 5
    # re-measured on 752 realistic seeded ones (docs/EXPERIMENTS.md): 0.51 wrongly refused 26%
    # of answerable questions, 0.45 refuses 10% and lets 19% of off-topic ones reach the
    # grounded LLM. Re-check on the Day 6 evaluation set once the whole pipeline runs.
    low_confidence_threshold: float = 0.45
    low_confidence_passages: int = 2
    chat_temperature: float = 0.2
    # Output budgets. Reasoning models (gpt-oss) spend ~100-400 of these on hidden thinking
    # before the visible answer, so they're sized well above the answer itself. A reply that
    # still hits the cap is treated as a failure (llm.py), never stored half-written.
    chat_max_tokens: int = 1500
    topic_name_max_tokens: int = 600
    severity_max_tokens: int = 900
    recommend_max_tokens: int = 2000
    summary_max_tokens: int = 1500
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
    # Load the embedding model and Chroma at startup instead of on the first request.
    warm_models_on_startup: bool = True
    chroma_path: str = "./data/chroma"  # ":memory:" = in-process, nothing on disk (tests)
    chroma_collection: str = "chunks"

    # Analytics batch (SPEC section 7).
    umap_neighbours: int = 12  # capped at n - 1
    umap_components: int = 5  # capped at n - 2
    umap_min_dist: float = 0.0  # pack similar points tightly: good for clustering, bad for plots
    umap_random_state: int = 42  # reproducible runs (costs UMAP's parallelism)
    umap_compatibility_layout: bool = True  # standard UMAP layout; pinned before the default changes
    hdbscan_min_cluster_size: int = 6  # tuned on Day 5 (docs/EXPERIMENTS.md): 4/6/8/10 swept
    hdbscan_min_samples: int = 2
    topic_keywords: int = 6
    topic_name_samples: int = 8
    topic_name_max_words: int = 8
    topic_match_threshold: float = 0.72  # cosine between centroids = "same topic as last month"
    trend_emerging_growth: float = 0.60
    trend_emerging_max_previous: int = 25
    trend_recurring_ratio: float = 0.7
    trend_declining_ratio: float = 0.5
    priority_weight_volume: float = 0.30
    priority_weight_growth: float = 0.30
    priority_weight_confidence: float = 0.25
    priority_weight_severity: float = 0.15
    priority_growth_cap: float = 3.0  # growth of 300%+ counts as "maximally rising"
    severity_base: float = 0.35
    severity_hard_step: float = 0.10
    severity_soft_step: float = 0.05
    severity_min: float = 0.05
    severity_samples: int = 6
    recommendation_count: int = 6
    recommendation_supporting_queries: int = 5
    category_product_severity: float = 0.65
    category_faq_max_severity: float = 0.5
    category_issue_severity: float = 0.6
    category_issue_min_count: int = 6
    category_issue_median_share: float = 0.4
    category_fallback_product_severity: float = 0.55

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
