import asyncio
import hashlib
import logging
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.chroma import delete_vectors_for_file
from core.config import settings
from models.auth import User
from models.conversation import ConversationList
from models.file_model import FileRecord
from models.ingestion import IngestionJob
from schema.file import UploadResponse
from tasks.ingestion_tasks import cleanup_orphaned_vectors, run_ingestion

logger = logging.getLogger(__name__)

_DEFAULT_UPLOAD_DIR = Path(__file__).resolve().parents[2] / "files"
UPLOAD_DIR = Path(settings.upload_dir) if settings.upload_dir else _DEFAULT_UPLOAD_DIR
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_TERMINAL_STATUSES = {IngestionJob.STATUS_COMPLETE, IngestionJob.STATUS_FAILED_PERMANENT}


def _save_and_hash(src_file, dest_path: Path) -> str:
    """Write src_file to dest_path and return its SHA-256 hex digest.

    Runs in a thread pool via asyncio.to_thread to avoid blocking the event loop
    during large file uploads (up to MAX_FILE_SIZE_MB).
    """
    with dest_path.open("wb") as buf:
        shutil.copyfileobj(src_file, buf)
    sha = hashlib.sha256()
    with dest_path.open("rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            sha.update(block)
    return sha.hexdigest()


async def upload_files(file: UploadFile, db: AsyncSession, current_user: User, description: str | None) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected")

    generated_name = f"{uuid4().hex}_{file.filename}"
    saved_path = UPLOAD_DIR / generated_name

    file_hash = await asyncio.to_thread(_save_and_hash, file.file, saved_path)

    # Per-user disk quota — reject before any DB work if over limit
    if settings.max_user_storage_mb > 0:
        # pg_advisory_xact_lock serializes concurrent uploads per user so the
        # quota read + insert are atomic. Released on transaction end.
        await db.execute(
            text("SELECT pg_advisory_xact_lock(:uid)").bindparams(uid=current_user.id)
        )
        result = await db.execute(
            select(func.sum(FileRecord.filesize)).where(
                FileRecord.user_id == current_user.id,
                FileRecord.is_active == True,  # noqa: E712
            )
        )
        used_bytes: int = result.scalar() or 0
        limit_bytes = settings.max_user_storage_mb * 1024 * 1024
        if used_bytes + saved_path.stat().st_size > limit_bytes:
            saved_path.unlink(missing_ok=True)
            used_mb = used_bytes // (1024 * 1024)
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Storage quota exceeded. "
                    f"You are using {used_mb} MB of {settings.max_user_storage_mb} MB allowed."
                ),
            )

    # Active duplicate — same content already live for this user
    result = await db.execute(
        select(FileRecord).where(
            FileRecord.user_id == current_user.id,
            FileRecord.file_hash == file_hash,
            FileRecord.is_active == True,  # noqa: E712
        )
    )
    active_dup = result.scalars().first()
    if active_dup is not None:
        saved_path.unlink(missing_ok=True)
        convo_result = await db.execute(
            select(ConversationList).where(
                ConversationList.file_id == active_dup.id,
                ConversationList.is_active == True,  # noqa: E712
            )
        )
        convo = convo_result.scalars().first()
        raise HTTPException(
            status_code=409,
            detail={
                "message": "This file already exists in your library.",
                "file_id": active_dup.id,
                "conversation_id": convo.id if convo else None,
            },
        )

    # Soft-deleted duplicate — reactivate and create a new conversation, no re-ingestion needed
    result = await db.execute(
        select(FileRecord).where(
            FileRecord.user_id == current_user.id,
            FileRecord.file_hash == file_hash,
            FileRecord.is_active == False,  # noqa: E712
        )
    )
    soft_dup = result.scalars().first()

    if soft_dup is not None:
        soft_dup_disk_path = UPLOAD_DIR / Path(soft_dup.filepath).name
        if not soft_dup_disk_path.exists():
            # Disk file was cleaned up manually; treat as a new upload instead of reactivating.
            soft_dup = None

    if soft_dup is not None:
        saved_path.unlink(missing_ok=True)
        soft_dup.is_active = True
        convo = ConversationList(
            user_id=current_user.id,
            conversation_title=file.filename,
            conversation_type="per_file",
            file_id=soft_dup.id,
            is_active=True,
        )
        db.add(convo)
        await db.commit()
        await db.refresh(soft_dup)
        await db.refresh(convo)
        return UploadResponse(
            id=soft_dup.id,
            filename=soft_dup.filename,
            filesize=soft_dup.filesize,
            ingestion_status=soft_dup.ingestion_status,
            conversation_id=convo.id,
            reactivated=True,
        )

    # New file — create FileRecord + per_file conversation atomically
    db_record = FileRecord(
        user_id=current_user.id,
        filename=file.filename,
        filepath=f"/files/{generated_name}",
        file_type=file.content_type,
        filesize=saved_path.stat().st_size,
        description=description,
        ingestion_status=IngestionJob.STATUS_QUEUED,
        file_hash=file_hash,
    )
    db.add(db_record)

    try:
        await db.flush()  # assigns db_record.id; raises IntegrityError on hash collision
    except IntegrityError:
        await db.rollback()
        saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail="A file with this content was just uploaded.")

    convo = ConversationList(
        user_id=current_user.id,
        conversation_title=file.filename,
        conversation_type="per_file",
        file_id=db_record.id,
        is_active=True,
    )
    db.add(convo)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail="A file with this content was just uploaded.")

    await db.refresh(db_record)
    await db.refresh(convo)

    # don't dispatch a second task if a rapid client retry beats us here
    result = await db.execute(
        select(IngestionJob).where(
            IngestionJob.file_id == db_record.id,
            IngestionJob.status.notin_(_TERMINAL_STATUSES),
        )
    )
    existing_job = result.scalars().first()
    if existing_job is not None:
        logger.warning(
            "Active ingestion job %s already exists for file %s; skipping duplicate dispatch.",
            existing_job.id, db_record.id,
        )
        return UploadResponse(
            id=db_record.id,
            filename=db_record.filename,
            filesize=db_record.filesize,
            ingestion_status=db_record.ingestion_status,
            conversation_id=convo.id,
        )

    try:
        job = IngestionJob(file_id=db_record.id, status=IngestionJob.STATUS_QUEUED)
        db.add(job)
        await db.commit()
        await db.refresh(job)
    except IntegrityError:
        await db.rollback()
        logger.warning("IntegrityError creating IngestionJob for file %s; duplicate guard hit.", db_record.id)
        return UploadResponse(
            id=db_record.id,
            filename=db_record.filename,
            filesize=db_record.filesize,
            ingestion_status=db_record.ingestion_status,
            conversation_id=convo.id,
        )

    result_task = run_ingestion.delay(job.id, db_record.id)
    job.celery_task_id = result_task.id
    await db.commit()

    return UploadResponse(
        id=db_record.id,
        filename=db_record.filename,
        filesize=db_record.filesize,
        ingestion_status=db_record.ingestion_status,
        conversation_id=convo.id,
    )


async def delete_file(file_id: int, user_id: int | None, db: AsyncSession) -> dict:
    result = await db.execute(select(FileRecord).where(FileRecord.id == file_id))
    record = result.scalars().first()
    if record is None or (user_id is not None and record.user_id != user_id):
        raise HTTPException(status_code=404, detail="File not found")

    # CASCADE cleans up postgres rows but chroma vectors need a manual delete
    try:
        delete_vectors_for_file(file_id, record.user_id)
    except Exception:
        # ChromaDB unavailable — queue a retrying background task so vectors aren't permanently orphaned
        logger.warning("ChromaDB delete failed for file %s; queuing async cleanup.", file_id)
        cleanup_orphaned_vectors.delay(file_id, record.user_id)

    filename_on_disk = Path(record.filepath).name
    disk_path = UPLOAD_DIR / filename_on_disk
    if disk_path.exists():
        disk_path.unlink()

    db.delete(record)
    await db.commit()
    return {"message": "File deleted successfully"}


async def reingest_file(file_id: int, user_id: int, db: AsyncSession) -> dict:
    result = await db.execute(select(FileRecord).where(FileRecord.id == file_id))
    record = result.scalars().first()
    if record is None or record.user_id != user_id:
        raise HTTPException(status_code=404, detail="File not found")

    if record.ingestion_status == IngestionJob.STATUS_COMPLETE:
        raise HTTPException(status_code=409, detail="File is already fully ingested")

    if record.ingestion_status not in (None, IngestionJob.STATUS_FAILED_PERMANENT):
        raise HTTPException(
            status_code=409,
            detail=f"Ingestion is already in progress (status: {record.ingestion_status})",
        )

    record.ingestion_status = IngestionJob.STATUS_QUEUED
    job = IngestionJob(file_id=record.id, status=IngestionJob.STATUS_QUEUED)
    db.add(job)
    await db.commit()
    await db.refresh(job)

    result_task = run_ingestion.delay(job.id, record.id)
    job.celery_task_id = result_task.id
    await db.commit()

    return {"message": "Re-ingestion started", "job_id": job.id}


