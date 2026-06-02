from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, model_validator

load_dotenv()


class Settings(BaseModel):
    # auth / db
    secret_key: str = os.getenv("SECRET_KEY", "")
    algorithm: str = os.getenv("ALGORITHM", "HS256")
    database: str = os.getenv("DATABASE", "")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    chat_data_ttl_seconds:int = int(os.getenv("CHAT_DATA_TTL_SECONDS",'3600'))

    # Set true in multi-worker production: startup aborts if Redis is unreachable.
    require_redis: bool = os.getenv("REQUIRE_REDIS", "false").lower() == "true"

    # Set false in multi-worker production and run 'alembic upgrade head' as a pre-start step.
    run_migrations_on_startup: bool = os.getenv("RUN_MIGRATIONS_ON_STARTUP", "true").lower() == "true"
    
    google_client_id: Optional[str] = os.getenv("GOOGLE_CLIENT_ID")
    google_client_secret: Optional[str] = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_url: Optional[str] = os.getenv("REDIRECT_URL")
    frontend_url: Optional[str] = os.getenv("FRONTEND_URL")

    rabbitmq_url: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")
    chat_flush_interval_seconds: int = int(os.getenv("CHAT_FLUSH_INTERVAL_SECONDS", "3600"))
    chat_stream_chunk_size: int = int(os.getenv("CHAT_STREAM_CHUNK_SIZE", "12"))
    chat_stream_ttl_seconds: int = int(os.getenv("CHAT_STREAM_TTL_SECONDS", "300"))

    # LLM / embeddings
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    openai_embedding_model: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    openai_chat_model: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
    llm_summary_temperature: float = float(os.getenv("LLM_SUMMARY_TEMPERATURE", "0.1"))

    # chroma
    chroma_host: str = os.getenv("CHROMA_HOST", "localhost")
    chroma_port: int = int(os.getenv("CHROMA_PORT", "8001"))
    chroma_collection_child_chunks: str = os.getenv("CHROMA_COLLECTION_CHILD_CHUNKS", "child_chunks")
    chroma_collection_summaries: str = os.getenv("CHROMA_COLLECTION_SUMMARIES", "document_summaries")
    chroma_collection_propositions: str = os.getenv("CHROMA_COLLECTION_PROPOSITIONS", "propositions")

    # celery / redis
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    celery_result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

    # ingestion limits
    max_file_size_mb: int = int(os.getenv("MAX_FILE_SIZE_MB", "200"))
    max_pages_per_doc: int = int(os.getenv("MAX_PAGES_PER_DOC", "500"))
    parent_chunk_size: int = int(os.getenv("PARENT_CHUNK_SIZE", "1800"))
    parent_chunk_overlap: int = int(os.getenv("PARENT_CHUNK_OVERLAP", "200"))
    child_chunk_size: int = int(os.getenv("CHILD_CHUNK_SIZE", "400"))
    child_chunk_overlap: int = int(os.getenv("CHILD_CHUNK_OVERLAP", "60"))
    embedding_batch_size: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "100"))

    # scanned PDF / near-empty document detection
    scanned_pdf_min_file_size_bytes: int = int(os.getenv("SCANNED_PDF_MIN_FILE_SIZE_BYTES", "51200"))
    scanned_pdf_text_density_threshold: float = float(os.getenv("SCANNED_PDF_TEXT_DENSITY_THRESHOLD", "0.001"))

    # summarization
    summary_short_doc_threshold: int = int(os.getenv("SUMMARY_SHORT_DOC_THRESHOLD", "12000"))
    summary_window_size: int = int(os.getenv("SUMMARY_WINDOW_SIZE", "10000"))
    summary_extraction_concurrency: int = int(os.getenv("SUMMARY_EXTRACTION_CONCURRENCY", "5"))

    # SemanticChunker
    use_semantic_chunker: bool = os.getenv("USE_SEMANTIC_CHUNKER", "false").lower() == "true"

    # proposition extraction
    use_proposition_extraction: bool = os.getenv("USE_PROPOSITION_EXTRACTION", "false").lower() == "true"
    proposition_extraction_concurrency: int = int(os.getenv("PROPOSITION_EXTRACTION_CONCURRENCY", "5"))

    # allowed MIME types for upload
    allowed_mime_types: list[str] = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "text/plain",
        "text/csv",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    ]

    # file upload directory; falls back to project-relative "files/" if not set
    upload_dir: str = os.getenv("UPLOAD_DIR", "")

    # retrieval quality
    retrieval_min_score: float = float(os.getenv("RETRIEVAL_MIN_SCORE", "0.0"))
    retrieval_history_context_turns: int = int(os.getenv("RETRIEVAL_HISTORY_CONTEXT_TURNS", "2"))

    # chat history window
    chat_history_turns: int = int(os.getenv("CHAT_HISTORY_TURNS", "6"))
    chat_history_max_chars: int = int(os.getenv("CHAT_HISTORY_MAX_CHARS", "8000"))

    # per-user storage quota; 0 = unlimited
    max_user_storage_mb: int = int(os.getenv("MAX_USER_STORAGE_MB", "0"))

    # ingestion job watchdog — jobs stuck longer than this are marked FAILED_PERMANENT
    ingestion_job_timeout_minutes: int = int(os.getenv("INGESTION_JOB_TIMEOUT_MINUTES", "30"))

    # max tokens to inject as document context into the chat prompt (leaves headroom for history + response)
    chat_max_context_tokens: int = int(os.getenv("CHAT_MAX_CONTEXT_TOKENS", "8000"))

    # Set true when running behind a reverse proxy (nginx, ALB, Caddy) so that
    # X-Forwarded-For is trusted for rate-limiting and IP logging.
    trust_proxy_headers: bool = os.getenv("TRUST_PROXY_HEADERS", "false").lower() == "true"

    # CORS — comma-separated list read from env
    cors_allowed_origins: list[str] = [
        o.strip()
        for o in os.getenv(
            "CORS_ALLOWED_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if o.strip()
    ]

    # Set false to close self-registration (e.g. invite-only or fully admin-managed prod).
    registration_open: bool = os.getenv("REGISTRATION_OPEN", "true").lower() == "true"

    # Set true in production so the session cookie is only sent over HTTPS.
    session_https_only: bool = os.getenv("SESSION_HTTPS_ONLY", "false").lower() == "true"

    # Comma-separated trusted proxy IPs for X-Forwarded-For; set to your LB IP(s) in production.
    trusted_proxy_ips: str = os.getenv("TRUSTED_PROXY_IPS", "*")

    # admin panel credentials (required — missing values fail startup)
    admin_username: str = os.getenv("ADMIN_USERNAME", "")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "")

    @model_validator(mode="after")
    def _validate_required_secrets(self) -> "Settings":
        missing = []
        if not self.secret_key:
            missing.append("SECRET_KEY")
        if not self.database:
            missing.append("DATABASE")
        if not self.openai_api_key:
            missing.append("OPENAI_API_KEY")
        if not self.admin_username:
            missing.append("ADMIN_USERNAME")
        if not self.admin_password:
            missing.append("ADMIN_PASSWORD")
        if missing:
            raise ValueError(
                f"Required environment variables are not set: {', '.join(missing)}. "
                "The application cannot start safely without these values."
            )

        # Fail fast on partial Google OAuth config — all four vars must be set together or not at all.
        google_vars = {
            "GOOGLE_CLIENT_ID": self.google_client_id,
            "GOOGLE_CLIENT_SECRET": self.google_client_secret,
            "REDIRECT_URL": self.redirect_url,
            "FRONTEND_URL": self.frontend_url,
        }
        set_vars = [k for k, v in google_vars.items() if v]
        unset_vars = [k for k, v in google_vars.items() if not v]
        if set_vars and unset_vars:
            raise ValueError(
                f"Partial Google OAuth configuration: {set_vars} are set but {unset_vars} are missing. "
                "Either set all four or none."
            )

        return self


settings = Settings()
