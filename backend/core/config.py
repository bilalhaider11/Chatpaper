from typing import Optional

from pydantic import BaseModel
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseModel):
    # auth / db
    secret_key: str = os.getenv("SECRET_KEY", "")
    algorithm: str = os.getenv("ALGORITHM", "HS256")
    database: str = os.getenv("DATABASE", "")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

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
    # Only applied to files larger than the min size; tiny files are allowed through.
    scanned_pdf_min_file_size_bytes: int = int(os.getenv("SCANNED_PDF_MIN_FILE_SIZE_BYTES", "51200"))
    scanned_pdf_text_density_threshold: float = float(os.getenv("SCANNED_PDF_TEXT_DENSITY_THRESHOLD", "0.001"))

    # short docs get one LLM call; anything longer is windowed and map-reduced
    summary_short_doc_threshold: int = int(os.getenv("SUMMARY_SHORT_DOC_THRESHOLD", "12000"))
    summary_window_size: int = int(os.getenv("SUMMARY_WINDOW_SIZE", "10000"))

    # SemanticChunker uses embedding similarity for topic boundaries; disabled by default
    use_semantic_chunker: bool = os.getenv("USE_SEMANTIC_CHUNKER", "false").lower() == "true"

    # proposition extraction adds atomic factual statements to a separate ChromaDB collection; off by default
    use_proposition_extraction: bool = os.getenv("USE_PROPOSITION_EXTRACTION", "false").lower() == "true"

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


settings = Settings()
