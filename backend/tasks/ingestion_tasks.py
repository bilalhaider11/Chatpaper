"""
Celery pipeline that processes an uploaded document through 6 stages:
parse → hash/dedup → parent chunks → child chunks → embed → summarize.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
except ImportError:
    RecursiveCharacterTextSplitter = None  # type: ignore[assignment,misc]
    ChatOpenAI = None  # type: ignore[assignment,misc]
    OpenAIEmbeddings = None  # type: ignore[assignment,misc]
    HumanMessage = None  # type: ignore[assignment,misc]
    SystemMessage = None  # type: ignore[assignment,misc]

from sqlalchemy.orm import Session

from core.celery_app import celery_app
from core.chroma import get_child_chunks_collection, get_document_summaries_collection
from core.config import settings
from core.database import SessionLocal
from models.file_model import FileRecord
from models.ingestion import DocumentParent, IngestionJob

logger = logging.getLogger(__name__)

FILES_DIR = Path(__file__).resolve().parents[2] / "files"


# status helpers

def _set_stage(job: IngestionJob, db: Session, stage: int) -> None:
    job.status = f"STAGE_{stage}"
    job.current_stage = stage
    if stage == 1:
        job.started_at = datetime.now(timezone.utc)
    db.commit()


def _complete(job: IngestionJob, db: Session, file_hash: str) -> None:
    job.status = IngestionJob.STATUS_COMPLETE
    job.current_stage = job.total_stages
    job.file_hash = file_hash
    job.completed_at = datetime.now(timezone.utc)
    db.commit()


def _fail_permanent(job: IngestionJob, db: Session, message: str, error_type: str) -> None:
    job.status = IngestionJob.STATUS_FAILED_PERMANENT
    job.error_message = message
    job.error_type = error_type
    job.completed_at = datetime.now(timezone.utc)
    db.commit()


def _fail_retryable(job: IngestionJob, db: Session, message: str, error_type: str) -> None:
    job.status = IngestionJob.STATUS_FAILED_RETRYABLE
    job.error_message = message
    job.error_type = error_type
    job.retry_count += 1
    db.commit()


# stage implementations

def _stage_parse(file_path: Path, content_type: str | None) -> tuple[str, int, list[str]]:
    from unstructured.partition.auto import partition  # lazy import — needs tesseract/libmagic at runtime

    elements = partition(filename=str(file_path))

    element_types: list[str] = list({
        getattr(el, "category", type(el).__name__)
        for el in elements
    })

    page_count = max(
        (getattr(el.metadata, "page_number", None) or 1 for el in elements),
        default=1,
    )

    raw_text = "\n\n".join(
        el.text for el in elements if getattr(el, "text", "").strip()
    )
    return raw_text, page_count, element_types


def _stage_hash(file_path: Path) -> str:
    """SHA-256 in 64 KB blocks so large PDFs don't blow memory."""
    sha = hashlib.sha256()
    with file_path.open("rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            sha.update(block)
    return sha.hexdigest()


def _stage_parent_chunk(raw_text: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.parent_chunk_size,
        chunk_overlap=settings.parent_chunk_overlap,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    return splitter.split_text(raw_text)


def _stage_child_chunk(parent_texts: list[str]) -> list[tuple[str, list[str]]]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.child_chunk_size,
        chunk_overlap=settings.child_chunk_overlap,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    return [(parent, splitter.split_text(parent)) for parent in parent_texts]


def _stage_embed_upsert(
    file_id: int,
    file_hash: str,
    parents_with_children: list[tuple[str, list[str]]],
    db: Session,
) -> None:
    embedder = OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        api_key=settings.openai_api_key,
    )
    collection = get_child_chunks_collection()

    for chunk_index, (parent_text, children) in enumerate(parents_with_children):
        parent_id = hashlib.sha256(f"{file_hash}:{chunk_index}".encode()).hexdigest()

        db.merge(DocumentParent(
            id=parent_id,
            file_id=file_id,
            content=parent_text,
            chunk_index=chunk_index,
        ))

        if not children:
            continue

        child_ids = [f"{parent_id}:{i}" for i in range(len(children))]
        child_metas = [
            {
                "file_id": file_id,
                "parent_id": parent_id,
                "child_index": i,
                "chunk_index": chunk_index,
            }
            for i in range(len(children))
        ]

        for batch_start in range(0, len(children), settings.embedding_batch_size):
            batch_texts = children[batch_start: batch_start + settings.embedding_batch_size]
            batch_ids = child_ids[batch_start: batch_start + settings.embedding_batch_size]
            batch_metas = child_metas[batch_start: batch_start + settings.embedding_batch_size]

            embeddings = embedder.embed_documents(batch_texts)
            collection.upsert(
                ids=batch_ids,
                documents=batch_texts,
                embeddings=embeddings,
                metadatas=batch_metas,
            )

    db.commit()


def _stage_summarize(file_id: int, file_hash: str, raw_text: str) -> None:
    llm = ChatOpenAI(
        model=settings.openai_chat_model,
        temperature=settings.llm_summary_temperature,
        api_key=settings.openai_api_key,
    )
    embedder = OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        api_key=settings.openai_api_key,
    )

    messages = [
        SystemMessage(content=(
            "You are a research assistant. Summarize the following document in 3-5 sentences, "
            "covering the main topic, key findings, and intended audience."
        )),
        HumanMessage(content=raw_text[:12_000]),
    ]
    summary: str = llm.invoke(messages).content

    embedding = embedder.embed_documents([summary])[0]
    collection = get_document_summaries_collection()
    collection.upsert(
        ids=[f"summary:{file_hash}"],
        documents=[summary],
        embeddings=[embedding],
        metadatas=[{"file_id": file_id, "file_hash": file_hash}],
    )


# Celery task

@celery_app.task(
    bind=True,
    name="tasks.ingestion_tasks.run_ingestion",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def run_ingestion(self, job_id: int, file_id: int) -> dict[str, Any]:
    db: Session = SessionLocal()
    try:
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if job is None:
            raise ValueError(f"IngestionJob {job_id} not found")

        file_record = db.query(FileRecord).filter(FileRecord.id == file_id).first()
        if file_record is None:
            _fail_permanent(job, db, f"FileRecord {file_id} not found", "FileNotFoundError")
            return {"status": "FAILED_PERMANENT", "reason": "file_record_missing"}

        # Stage 1 — Parse
        _set_stage(job, db, 1)
        file_path = FILES_DIR / Path(file_record.filepath).name
        if not file_path.exists():
            _fail_permanent(job, db, f"File not on disk: {file_path}", "FileNotFoundError")
            return {"status": "FAILED_PERMANENT", "reason": "file_missing_on_disk"}

        raw_text, page_count, element_types = _stage_parse(file_path, file_record.file_type)
        job.total_pages = page_count
        file_record.total_pages = page_count
        db.commit()

        # Stage 2 — Hash / dedup
        _set_stage(job, db, 2)
        file_hash = _stage_hash(file_path)
        job.file_hash = file_hash
        job.file_size_bytes = file_path.stat().st_size
        file_record.file_hash = file_hash
        db.commit()

        existing = db.query(DocumentParent).filter(DocumentParent.file_id == file_id).first()
        if existing is not None:
            _complete(job, db, file_hash)
            file_record.ingestion_status = IngestionJob.STATUS_COMPLETE
            db.commit()
            return {"status": "COMPLETE", "deduped": True}

        # Stage 3 — Parent chunks
        _set_stage(job, db, 3)
        parent_texts = _stage_parent_chunk(raw_text)

        # Stage 4 — Child chunks
        _set_stage(job, db, 4)
        parents_with_children = _stage_child_chunk(parent_texts)

        # Stage 5 — Embed + upsert
        _set_stage(job, db, 5)
        _stage_embed_upsert(file_id, file_hash, parents_with_children, db)

        # Stage 6 — Summary
        _set_stage(job, db, 6)
        _stage_summarize(file_id, file_hash, raw_text)

        _complete(job, db, file_hash)
        file_record.ingestion_status = IngestionJob.STATUS_COMPLETE
        db.commit()

        return {"status": "COMPLETE", "job_id": job_id, "chunks": len(parent_texts)}

    except Exception as exc:
        logger.exception(
            "Ingestion failed for job %s, attempt %d/%d",
            job_id, self.request.retries, self.max_retries,
        )
        db.rollback()
        try:
            job_fresh = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
            if job_fresh:
                if self.request.retries < self.max_retries:
                    _fail_retryable(job_fresh, db, str(exc), type(exc).__name__)
                else:
                    _fail_permanent(job_fresh, db, str(exc), type(exc).__name__)
        except Exception:
            logger.exception("Could not update job status after failure for job %s", job_id)

        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        raise
    finally:
        db.close()
