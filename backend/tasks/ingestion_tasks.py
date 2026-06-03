from __future__ import annotations

import dataclasses
import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

try:
    import openai as _openai
except ImportError:
    _openai = None  # type: ignore[assignment]

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_core.messages import HumanMessage, SystemMessage
except ImportError:
    RecursiveCharacterTextSplitter = None  # type: ignore[assignment,misc]
    HumanMessage = None  # type: ignore[assignment,misc]
    SystemMessage = None  # type: ignore[assignment,misc]

from sqlalchemy.orm import Session

from core.celery_app import celery_app
from core.chroma import get_child_chunks_collection, get_document_summaries_collection, get_propositions_collection
from core.config import settings
from core.database import SessionLocal
from core.llm import get_chat_llm, get_embedder
from models.file_model import FileRecord
from models.ingestion import DocumentParent, IngestionJob

logger = logging.getLogger(__name__)

_DEFAULT_FILES_DIR = Path(__file__).resolve().parents[2] / "files"
FILES_DIR = Path(settings.upload_dir) if settings.upload_dir else _DEFAULT_FILES_DIR

_TABULAR_MIMES = {
    "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
}

_rate_limit_exc = (_openai.RateLimitError,) if _openai is not None else (Exception,)


@retry(
    retry=retry_if_exception_type(_rate_limit_exc),
    wait=wait_exponential(multiplier=1, min=10, max=300),
    stop=stop_after_attempt(5),
    reraise=True,
)
def _embed_with_backoff(embedder: Any, texts: list[str]) -> list[list[float]]:
    return embedder.embed_documents(texts)


@dataclasses.dataclass
class ParsedElement:
    text: str
    page_number: int
    element_type: str


@dataclasses.dataclass
class ParentChunk:
    text: str
    chunk_index: int
    page_start: int
    page_end: int
    element_types: str  # comma-separated, e.g. "NarrativeText,Table"


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

def _parse_tabular(file_path: Path, content_type: str) -> list[ParsedElement]:
    import pandas as pd

    try:
        if content_type == "text/csv":
            frames: dict[str, Any] = {"data": pd.read_csv(file_path)}
        else:
            raw = pd.read_excel(file_path, sheet_name=None)
            frames = raw if isinstance(raw, dict) else {"Sheet1": raw}
    except pd.errors.ParserError as exc:
        raise ValueError(f"malformed CSV/XLSX: {exc}") from exc
    except Exception as exc:
        raise ValueError(f"could not open tabular file: {exc}") from exc

    result: list[ParsedElement] = []
    rows_per_chunk = 50
    for frame in frames.values():
        frame = frame.dropna(how="all")
        if frame.empty:
            continue
        for row_start in range(0, len(frame), rows_per_chunk):
            chunk_df = frame.iloc[row_start: row_start + rows_per_chunk]
            try:
                text = chunk_df.to_markdown(index=False)
            except Exception:
                text = chunk_df.to_string(index=False)
            result.append(ParsedElement(text=text, page_number=1, element_type="Table"))

    if not result:
        raise ValueError("tabular file contains no data rows")
    return result


def _stage_parse(file_path: Path, content_type: str | None) -> list[ParsedElement]:
    if content_type in _TABULAR_MIMES:
        return _parse_tabular(file_path, content_type or "")

    encoding_hint: str | None = None
    if content_type == "text/plain":
        import chardet
        raw_bytes = file_path.read_bytes()[:10240]
        detected = chardet.detect(raw_bytes)
        if (detected.get("confidence") or 0) >= 0.7:
            encoding_hint = detected.get("encoding")
        else:
            logger.warning("low chardet confidence for %s (%s); using UTF-8", file_path.name, detected)
            encoding_hint = "utf-8"

    from unstructured.partition.auto import partition  # lazy import — needs tesseract/libmagic at runtime
    kwargs: dict[str, Any] = {}
    if encoding_hint:
        kwargs["encoding"] = encoding_hint
    elements = partition(filename=str(file_path), **kwargs)

    result: list[ParsedElement] = []
    for el in elements:
        text = getattr(el, "text", "").strip()
        if not text:
            continue
        page_num = getattr(el.metadata, "page_number", None) or 1
        category = getattr(el, "category", type(el).__name__)
        result.append(ParsedElement(text=text, page_number=page_num, element_type=category))
    return result


def _stage_hash(file_path: Path) -> str:
    """SHA-256 in 64 KB blocks so large PDFs don't blow memory."""
    sha = hashlib.sha256()
    with file_path.open("rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            sha.update(block)
    return sha.hexdigest()


def _stage_parent_chunk(parsed_elements: list[ParsedElement]) -> list[ParentChunk]:
    splitter: Any = None
    if settings.use_semantic_chunker:
        try:
            from langchain_experimental.text_splitter import SemanticChunker
            splitter = SemanticChunker(
                embeddings=get_embedder(),
                breakpoint_threshold_type="percentile",
            )
        except (ImportError, RuntimeError):
            pass  # langchain_experimental or langchain_openai missing — fall through to default splitter

    if splitter is None:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.parent_chunk_size,
            chunk_overlap=settings.parent_chunk_overlap,
            separators=["\n\n", "\n", ".", " ", ""],
        )

    parent_chunks: list[ParentChunk] = []
    chunk_index = 0
    i = 0

    while i < len(parsed_elements):
        el = parsed_elements[i]

        if el.element_type == "Table":
            # tables are atomic — never split across chunk boundaries
            if len(el.text) > settings.parent_chunk_size:
                logger.warning(
                    "table at page %d is %d chars (limit %d); keeping as single oversized chunk",
                    el.page_number, len(el.text), settings.parent_chunk_size,
                )
            parent_chunks.append(ParentChunk(
                text=el.text,
                chunk_index=chunk_index,
                page_start=el.page_number,
                page_end=el.page_number,
                element_types="Table",
            ))
            chunk_index += 1
            i += 1
        else:
            # collect contiguous non-table elements and split them together
            run: list[ParsedElement] = []
            while i < len(parsed_elements) and parsed_elements[i].element_type != "Table":
                run.append(parsed_elements[i])
                i += 1

            # track per-element char offsets so we can map each chunk back to page numbers
            parts: list[str] = []
            element_spans: list[tuple[int, int, int, str]] = []  # (start, end, page_num, etype)
            pos = 0
            for e in run:
                parts.append(e.text)
                element_spans.append((pos, pos + len(e.text), e.page_number, e.element_type))
                pos += len(e.text) + 2  # +2 for the "\n\n" separator

            raw_text = "\n\n".join(parts)
            chunk_texts = splitter.split_text(raw_text)

            search_start = 0
            for chunk_text in chunk_texts:
                chunk_pos = raw_text.find(chunk_text, search_start)
                if chunk_pos == -1:
                    if settings.use_semantic_chunker:
                        logger.warning(
                            "SemanticChunker produced a chunk not found in raw_text at "
                            "search_start=%d; page range may be inaccurate for this chunk",
                            search_start,
                        )
                    chunk_pos = search_start
                chunk_end = chunk_pos + len(chunk_text)
                search_start = chunk_pos + 1

                pages: list[int] = []
                etypes: list[str] = []
                seen: set[str] = set()
                for span_start, span_end, page_num, etype in element_spans:
                    if span_start < chunk_end and span_end > chunk_pos:
                        pages.append(page_num)
                        if etype not in seen:
                            etypes.append(etype)
                            seen.add(etype)

                parent_chunks.append(ParentChunk(
                    text=chunk_text,
                    chunk_index=chunk_index,
                    page_start=min(pages) if pages else 1,
                    page_end=max(pages) if pages else 1,
                    element_types=",".join(etypes),
                ))
                chunk_index += 1

    return parent_chunks


def _stage_child_chunk(parent_chunks: list[ParentChunk]) -> Iterator[tuple[ParentChunk, list[str]]]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.child_chunk_size,
        chunk_overlap=settings.child_chunk_overlap,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    for parent in parent_chunks:
        if parent.element_types == "Table":
            yield parent, [parent.text]  # tables must not be split further
        else:
            yield parent, splitter.split_text(parent.text)


def _stage_embed_upsert(
    file_id: int,
    user_id: int,
    file_hash: str,
    filename: str,
    file_type: str,
    language: str,
    parents_with_children: Iterator[tuple[ParentChunk, list[str]]],
    db: Session,
) -> None:
    embedder = get_embedder()
    collection = get_child_chunks_collection()

    for parent, children in parents_with_children:
        # user_id prefix ensures IDs are globally unique per user, preventing cross-user upsert collisions
        parent_id = hashlib.sha256(f"{user_id}:{file_hash}:{parent.chunk_index}".encode()).hexdigest()

        # resume from last uncommitted parent on retry
        existing = (
            db.query(DocumentParent)
            .filter(DocumentParent.id == parent_id)
            .first()
        )
        if existing is not None and existing.is_committed:
            continue

        db.merge(DocumentParent(
            id=parent_id,
            file_id=file_id,
            content=parent.text,
            chunk_index=parent.chunk_index,
            page_start=parent.page_start,
            page_end=parent.page_end,
            element_types=parent.element_types.split(",") if parent.element_types else [],
            embedding_model=settings.openai_embedding_model,
            is_committed=False,
        ))
        db.flush()

        if children:
            child_ids = [f"{parent_id}:{i}" for i in range(len(children))]
            child_metas = [
                {
                    "file_id": file_id,
                    "user_id": user_id,
                    "parent_id": parent_id,
                    "child_index": i,
                    "chunk_index": parent.chunk_index,
                    "page_start": parent.page_start,
                    "page_end": parent.page_end,
                    "element_types": parent.element_types,
                    "file_hash": file_hash,
                    "filename": filename,
                    "file_type": file_type or "",
                    "language": language,
                }
                for i in range(len(children))
            ]

            for batch_start in range(0, len(children), settings.embedding_batch_size):
                batch_texts = children[batch_start: batch_start + settings.embedding_batch_size]
                batch_ids = child_ids[batch_start: batch_start + settings.embedding_batch_size]
                batch_metas = child_metas[batch_start: batch_start + settings.embedding_batch_size]

                embeddings = _embed_with_backoff(embedder, batch_texts)
                collection.upsert(
                    ids=batch_ids,
                    documents=batch_texts,
                    embeddings=embeddings,
                    metadatas=batch_metas,
                )

        # chroma write done — safe to mark committed
        db.query(DocumentParent).filter(DocumentParent.id == parent_id).update({"is_committed": True})
        db.commit()


def _stage_summarize(
    file_id: int,
    user_id: int,
    file_hash: str,
    filename: str,
    language: str,
    raw_text: str,
) -> None:
    llm = get_chat_llm(temperature=settings.llm_summary_temperature)
    embedder = get_embedder()

    if len(raw_text) <= settings.summary_short_doc_threshold:
        messages = [
            SystemMessage(content=(
                "You are a research assistant. Summarize the following document in 3-5 sentences, "
                "covering the main topic, key findings, and intended audience."
            )),
            HumanMessage(content=raw_text),
        ]
        summary: str = llm.invoke(messages).content
    else:
        # map: summarize each window concurrently
        windows = [
            raw_text[i: i + settings.summary_window_size]
            for i in range(0, len(raw_text), settings.summary_window_size)
        ]

        def _summarize_window(window: str) -> str:
            return llm.invoke([
                SystemMessage(content="Summarize this section in 2 sentences."),
                HumanMessage(content=window),
            ]).content

        section_summaries: list[str] = [""] * len(windows)
        with ThreadPoolExecutor(max_workers=settings.summary_extraction_concurrency) as pool:
            future_to_idx = {pool.submit(_summarize_window, w): i for i, w in enumerate(windows)}
            for future in as_completed(future_to_idx):
                section_summaries[future_to_idx[future]] = future.result()

        # reduce: stitch section summaries into one (synchronous — single call)
        combined = "\n\n".join(section_summaries)
        reduce_msgs = [
            SystemMessage(content=(
                "Combine these section summaries into a single 3-5 sentence summary of the full document, "
                "covering the main topic, key findings, and intended audience."
            )),
            HumanMessage(content=combined),
        ]
        summary = llm.invoke(reduce_msgs).content

    embedding = _embed_with_backoff(embedder, [summary])[0]
    collection = get_document_summaries_collection()
    collection.upsert(
        ids=[f"summary:{user_id}:{file_hash}"],
        documents=[summary],
        embeddings=[embedding],
        metadatas=[{
            "file_id": file_id,
            "user_id": user_id,
            "file_hash": file_hash,
            "filename": filename,
            "language": language,
        }],
    )


def _stage_extract_propositions(
    file_id: int,
    user_id: int,
    file_hash: str,
    filename: str,
    language: str,
    db: Session,
) -> None:
    llm = get_chat_llm(temperature=0.0)
    embedder = get_embedder()
    collection = get_propositions_collection()
    parents = db.query(DocumentParent).filter(DocumentParent.file_id == file_id).all()

    def _extract_parent(parent: DocumentParent) -> None:
        raw: str = llm.invoke([
            SystemMessage(content=(
                "Extract every distinct factual statement from the text below as a numbered list. "
                "Each item must be a single self-contained sentence. "
                "Do not include vague or subjective claims. One proposition per line."
            )),
            HumanMessage(content=parent.content),
        ]).content
        propositions = [
            line.strip().lstrip("0123456789.) -•")
            for line in raw.splitlines()
            if line.strip()
        ]
        propositions = [p for p in propositions if p]
        if not propositions:
            return

        prop_ids = [f"prop:{parent.id}:{i}" for i in range(len(propositions))]
        prop_metas = [
            {
                "file_id": file_id,
                "user_id": user_id,
                "parent_id": parent.id,
                "prop_index": i,
                "file_hash": file_hash,
                "filename": filename,
                "language": language,
            }
            for i in range(len(propositions))
        ]
        for batch_start in range(0, len(propositions), settings.embedding_batch_size):
            batch_texts = propositions[batch_start: batch_start + settings.embedding_batch_size]
            batch_ids = prop_ids[batch_start: batch_start + settings.embedding_batch_size]
            batch_metas = prop_metas[batch_start: batch_start + settings.embedding_batch_size]
            embeddings = _embed_with_backoff(embedder, batch_texts)
            collection.upsert(ids=batch_ids, documents=batch_texts, embeddings=embeddings, metadatas=batch_metas)

    with ThreadPoolExecutor(max_workers=settings.proposition_extraction_concurrency) as pool:
        futures = [pool.submit(_extract_parent, parent) for parent in parents]
        for future in as_completed(futures):
            future.result()  # re-raise any extraction exception


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

        parsed_elements = _stage_parse(file_path, file_record.file_type)

        if not parsed_elements:
            _fail_permanent(
                job, db,
                "No text content could be extracted from this document.",
                "EMPTY_DOCUMENT",
            )
            file_record.ingestion_status = IngestionJob.STATUS_FAILED_PERMANENT
            db.commit()
            return {"status": "FAILED_PERMANENT", "reason": "empty_document"}

        raw_text = "\n\n".join(el.text for el in parsed_elements)
        page_count = max((el.page_number for el in parsed_elements), default=1)
        job.total_pages = page_count
        file_record.total_pages = page_count
        db.commit()

        # Enforce page limit before doing any expensive work.
        if page_count > settings.max_pages_per_doc:
            _fail_permanent(
                job, db,
                f"Document has {page_count} pages; maximum is {settings.max_pages_per_doc}.",
                "DOCUMENT_TOO_LONG",
            )
            file_record.ingestion_status = IngestionJob.STATUS_FAILED_PERMANENT
            db.commit()
            return {"status": "FAILED_PERMANENT", "reason": "document_too_long"}

        # scanned / image-only PDFs yield almost no text — skip them early
        file_size = file_path.stat().st_size
        text_density = len(raw_text.strip()) / max(file_size, 1)
        if (
            file_size >= settings.scanned_pdf_min_file_size_bytes
            and text_density < settings.scanned_pdf_text_density_threshold
        ):
            _fail_permanent(
                job, db,
                "Document appears to be scanned or contains no extractable text. "
                "OCR support is not currently available.",
                "LIKELY_SCANNED_PDF",
            )
            file_record.ingestion_status = IngestionJob.STATUS_FAILED_PERMANENT
            db.commit()
            return {"status": "FAILED_PERMANENT", "reason": "likely_scanned_pdf"}

        # Stage 2 — Hash / dedup
        _set_stage(job, db, 2)
        # reuse hash computed at upload time if available; avoids reading the full file twice
        file_hash = file_record.file_hash or _stage_hash(file_path)
        job.file_hash = file_hash
        job.file_size_bytes = file_path.stat().st_size
        file_record.file_hash = file_hash

        try:
            from langdetect import detect
            language: str = detect(raw_text[:2000])
        except Exception:
            language = "unknown"
        file_record.language = language
        db.commit()

        # same content uploaded again under a different name — skip re-embedding
        # is_active=True ensures soft-deleted records don't trigger a false dedup
        duplicate = (
            db.query(FileRecord)
            .filter(
                FileRecord.user_id == file_record.user_id,
                FileRecord.file_hash == file_hash,
                FileRecord.id != file_id,
                FileRecord.ingestion_status == IngestionJob.STATUS_COMPLETE,
                FileRecord.is_active == True,
            )
            .first()
        )
        if duplicate is not None:
            logger.info(
                "File %s is a duplicate of file %s (hash %s); skipping ingestion.",
                file_id, duplicate.id, file_hash,
            )
            _complete(job, db, file_hash)
            file_record.ingestion_status = IngestionJob.STATUS_COMPLETE
            db.commit()
            return {"status": "COMPLETE", "deduped": True, "original_file_id": duplicate.id}

        # Stage 3 — Parent chunks
        _set_stage(job, db, 3)
        parent_chunks = _stage_parent_chunk(parsed_elements)

        # Stage 4 — Child chunks
        _set_stage(job, db, 4)
        children_gen = _stage_child_chunk(parent_chunks)

        # Stage 5 — Embed + upsert
        _set_stage(job, db, 5)
        _stage_embed_upsert(
            file_id=file_id,
            user_id=file_record.user_id,
            file_hash=file_hash,
            filename=file_record.filename,
            file_type=file_record.file_type or "",
            language=language,
            parents_with_children=children_gen,
            db=db,
        )

        # Stage 6 — Summary
        _set_stage(job, db, 6)
        _stage_summarize(
            file_id=file_id,
            user_id=file_record.user_id,
            file_hash=file_hash,
            filename=file_record.filename,
            language=language,
            raw_text=raw_text,
        )

        # optional proposition extraction — runs silently, doesn't affect job status
        if settings.use_proposition_extraction:
            try:
                _stage_extract_propositions(
                    file_id=file_id,
                    user_id=file_record.user_id,
                    file_hash=file_hash,
                    filename=file_record.filename,
                    language=language,
                    db=db,
                )
            except Exception:
                logger.exception("proposition extraction failed for job %s — continuing", job_id)

        _complete(job, db, file_hash)
        file_record.ingestion_status = IngestionJob.STATUS_COMPLETE
        file_record.embedding_model = settings.openai_embedding_model
        db.commit()

        return {"status": "COMPLETE", "job_id": job_id, "chunks": len(parent_chunks)}

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
                    new_status = IngestionJob.STATUS_FAILED_RETRYABLE
                else:
                    _fail_permanent(job_fresh, db, str(exc), type(exc).__name__)
                    new_status = IngestionJob.STATUS_FAILED_PERMANENT
                    # Clean up partial writes that can never be completed.
                    db.query(DocumentParent).filter(
                        DocumentParent.file_id == file_id,
                        DocumentParent.is_committed == False,  # noqa: E712
                    ).delete()
                file_fresh = db.query(FileRecord).filter(FileRecord.id == file_id).first()
                if file_fresh:
                    file_fresh.ingestion_status = new_status
                    db.commit()
        except Exception:
            logger.exception("Could not update job status after failure for job %s", job_id)

        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        raise
    finally:
        db.close()


@celery_app.task(name="tasks.ingestion_tasks.cleanup_stuck_jobs")
def cleanup_stuck_jobs() -> dict:
    """Periodic watchdog: marks ingestion jobs that have been stuck in a non-terminal state
    longer than settings.ingestion_job_timeout_minutes as FAILED_PERMANENT."""
    db: Session = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.ingestion_job_timeout_minutes)
        terminal = {IngestionJob.STATUS_COMPLETE, IngestionJob.STATUS_FAILED_PERMANENT}
        stuck = (
            db.query(IngestionJob)
            .filter(
                IngestionJob.status.notin_(terminal),
                IngestionJob.updated_at < cutoff,
            )
            .all()
        )
        if not stuck:
            return {"marked": 0}

        for job in stuck:
            job.status = IngestionJob.STATUS_FAILED_PERMANENT
            job.error_message = (
                f"Job timed out after {settings.ingestion_job_timeout_minutes} minutes without progress."
            )
            job.error_type = "JobTimeout"
            job.completed_at = datetime.now(timezone.utc)
            file_rec = db.query(FileRecord).filter(FileRecord.id == job.file_id).first()
            if file_rec:
                file_rec.ingestion_status = IngestionJob.STATUS_FAILED_PERMANENT

        db.commit()
        logger.warning("cleanup_stuck_jobs: marked %d stuck job(s) as FAILED_PERMANENT", len(stuck))
        return {"marked": len(stuck)}
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="tasks.ingestion_tasks.cleanup_orphaned_vectors",
    max_retries=10,
    default_retry_delay=60,
    acks_late=True,
)
def cleanup_orphaned_vectors(self, file_id: int, user_id: int) -> None:
    """Retrying cleanup task queued when a synchronous ChromaDB delete fails during file deletion."""
    try:
        from core.chroma import delete_vectors_for_file
        delete_vectors_for_file(file_id, user_id)
    except Exception as exc:
        countdown = min(60 * (2 ** self.request.retries), 3600)
        raise self.retry(exc=exc, countdown=countdown)
