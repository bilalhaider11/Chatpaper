from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY

from core.database import Base


class DocumentParent(Base):
    __tablename__ = "document_parents"

    id = Column(String(64), primary_key=True)
    file_id = Column(Integer, ForeignKey("files_data.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    page_start = Column(Integer, nullable=True)
    page_end = Column(Integer, nullable=True)
    element_types = Column(ARRAY(Text), nullable=True)
    chunk_index = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    STATUS_QUEUED = "QUEUED"
    STATUS_STAGE_1 = "STAGE_1"
    STATUS_STAGE_2 = "STAGE_2"
    STATUS_STAGE_3 = "STAGE_3"
    STATUS_STAGE_4 = "STAGE_4"
    STATUS_STAGE_5 = "STAGE_5"
    STATUS_STAGE_6 = "STAGE_6"
    STATUS_COMPLETE = "COMPLETE"
    STATUS_FAILED_PERMANENT = "FAILED_PERMANENT"
    STATUS_FAILED_RETRYABLE = "FAILED_RETRYABLE"

    VALID_STATUSES = frozenset({
        "QUEUED",
        "STAGE_1", "STAGE_2", "STAGE_3", "STAGE_4", "STAGE_5", "STAGE_6",
        "COMPLETE", "FAILED_PERMANENT", "FAILED_RETRYABLE",
    })

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    file_id = Column(Integer, ForeignKey("files_data.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(30), nullable=False, default=STATUS_QUEUED)
    current_stage = Column(Integer, nullable=True)
    total_stages = Column(Integer, nullable=False, default=6)
    error_message = Column(Text, nullable=True)
    error_type = Column(String(100), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    celery_task_id = Column(String(255), nullable=True)
    file_hash = Column(String(64), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    total_pages = Column(Integer, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
