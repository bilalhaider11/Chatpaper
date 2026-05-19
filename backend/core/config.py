from typing import Optional

from pydantic import BaseModel
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseModel):
    # ── Existing auth / db ────────────────────────────────────────────────────
    secret_key: str = os.getenv("SECRET_KEY", "")
    algorithm: str = os.getenv("ALGORITHM", "HS256")
    database: str = os.getenv("DATABASE", "")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

    # ── LLM / Embeddings ─────────────────────────────────────────────────────
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    openai_embedding_model: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    openai_chat_model: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
    llm_summary_temperature: float = float(os.getenv("LLM_SUMMARY_TEMPERATURE", "0.1"))

    # ── ChromaDB ─────────────────────────────────────────────────────────────
    chroma_host: str = os.getenv("CHROMA_HOST", "localhost")
    chroma_port: int = int(os.getenv("CHROMA_PORT", "8001"))
    chroma_collection_child_chunks: str = os.getenv("CHROMA_COLLECTION_CHILD_CHUNKS", "child_chunks")
    chroma_collection_summaries: str = os.getenv("CHROMA_COLLECTION_SUMMARIES", "document_summaries")

    # ── Celery + Redis ────────────────────────────────────────────────────────
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    celery_result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

    # ── Ingestion limits ──────────────────────────────────────────────────────
    max_file_size_mb: int = int(os.getenv("MAX_FILE_SIZE_MB", "200"))
    max_pages_per_doc: int = int(os.getenv("MAX_PAGES_PER_DOC", "500"))
    parent_chunk_size: int = int(os.getenv("PARENT_CHUNK_SIZE", "1800"))
    parent_chunk_overlap: int = int(os.getenv("PARENT_CHUNK_OVERLAP", "200"))
    child_chunk_size: int = int(os.getenv("CHILD_CHUNK_SIZE", "400"))
    child_chunk_overlap: int = int(os.getenv("CHILD_CHUNK_OVERLAP", "60"))
    embedding_batch_size: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "100"))


settings = Settings()
