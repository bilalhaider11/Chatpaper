from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func

from core.database import Base


class FileRecord(Base):
    """Maps to `files_data` as defined in Alembic (column names differ from attribute names)."""

    __tablename__ = "files_data"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    filename = Column("file_name", String(255), nullable=False)
    filepath = Column("file_url", Text(), nullable=False)
    file_type = Column(String(100), nullable=True)
    filesize = Column("file_size", Integer(), nullable=True)
    description = Column(Text(), nullable=True)
    uploaded_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    is_active = Column("is_Active", Boolean, nullable=False, default=True)

    # Ingestion metadata
    file_hash = Column(String(64), nullable=True)
    document_version = Column(Integer, nullable=True)
    ingestion_status = Column(String(30), nullable=True)
    language = Column(String(10), nullable=True)
    total_pages = Column(Integer, nullable=True)
