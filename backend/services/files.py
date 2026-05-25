import hashlib
import logging
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.chroma import delete_vectors_for_file
from core.config import settings
from models.auth import User
from models.conversation import ConversationList
from models.file_model import FileRecord
from models.ingestion import IngestionJob
from schema.file import UploadResponse
from tasks.ingestion_tasks import run_ingestion

logger = logging.getLogger(__name__)

_DEFAULT_UPLOAD_DIR = Path(__file__).resolve().parents[2] / "files"
UPLOAD_DIR = Path(settings.upload_dir) if settings.upload_dir else _DEFAULT_UPLOAD_DIR
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_TERMINAL_STATUSES = {IngestionJob.STATUS_COMPLETE, IngestionJob.STATUS_FAILED_PERMANENT}


def _compute_file_hash(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            sha.update(block)
    return sha.hexdigest()


def upload_files(file: UploadFile, db: Session, current_user: User, description: str | None) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected")

    generated_name = f"{uuid4().hex}_{file.filename}"
    saved_path = UPLOAD_DIR / generated_name

    with saved_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_hash = _compute_file_hash(saved_path)

    # Active duplicate — same content already live for this user
    active_dup = (
        db.query(FileRecord)
        .filter(
            FileRecord.user_id == current_user.id,
            FileRecord.file_hash == file_hash,
            FileRecord.is_active == True,
        )
        .first()
    )
    if active_dup is not None:
        saved_path.unlink(missing_ok=True)
        convo = (
            db.query(ConversationList)
            .filter(
                ConversationList.file_id == active_dup.id,
                ConversationList.is_active == True,
            )
            .first()
        )
        raise HTTPException(
            status_code=409,
            detail={
                "message": "This file already exists in your library.",
                "file_id": active_dup.id,
                "conversation_id": convo.id if convo else None,
            },
        )

    # Soft-deleted duplicate — reactivate and create a new conversation, no re-ingestion needed
    soft_dup = (
        db.query(FileRecord)
        .filter(
            FileRecord.user_id == current_user.id,
            FileRecord.file_hash == file_hash,
            FileRecord.is_active == False,
        )
        .first()
    )
    if soft_dup is not None:
        saved_path.unlink(missing_ok=True)  # old disk copy is still present from original upload
        soft_dup.is_active = True
        convo = ConversationList(
            user_id=current_user.id,
            conversation_title=file.filename,
            conversation_type="per_file",
            file_id=soft_dup.id,
            is_active=True,
        )
        db.add(convo)
        db.commit()
        db.refresh(soft_dup)
        db.refresh(convo)
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
        db.flush()  # assigns db_record.id; raises IntegrityError on hash collision
    except IntegrityError:
        db.rollback()
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
        db.commit()
    except IntegrityError:
        db.rollback()
        saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail="A file with this content was just uploaded.")

    db.refresh(db_record)
    db.refresh(convo)

    # don't dispatch a second task if a rapid client retry beats us here
    existing_job = (
        db.query(IngestionJob)
        .filter(
            IngestionJob.file_id == db_record.id,
            IngestionJob.status.notin_(_TERMINAL_STATUSES),
        )
        .first()
    )
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
        db.commit()
        db.refresh(job)
    except IntegrityError:
        db.rollback()
        logger.warning("IntegrityError creating IngestionJob for file %s; duplicate guard hit.", db_record.id)
        return UploadResponse(
            id=db_record.id,
            filename=db_record.filename,
            filesize=db_record.filesize,
            ingestion_status=db_record.ingestion_status,
            conversation_id=convo.id,
        )

    result = run_ingestion.delay(job.id, db_record.id)
    job.celery_task_id = result.id
    db.commit()

    return UploadResponse(
        id=db_record.id,
        filename=db_record.filename,
        filesize=db_record.filesize,
        ingestion_status=db_record.ingestion_status,
        conversation_id=convo.id,
    )


def delete_file(file_id: int, user_id: int | None, db: Session) -> dict:
    record = db.query(FileRecord).filter(FileRecord.id == file_id).first()
    if record is None or (user_id is not None and record.user_id != user_id):
        raise HTTPException(status_code=404, detail="File not found")

    # CASCADE cleans up postgres rows but chroma vectors need a manual delete
    try:
        delete_vectors_for_file(file_id, record.user_id)
    except Exception:
        logger.warning("Could not delete ChromaDB vectors for file %s; continuing with DB delete.", file_id)

    filename_on_disk = Path(record.filepath).name
    disk_path = UPLOAD_DIR / filename_on_disk
    if disk_path.exists():
        disk_path.unlink()

    db.delete(record)
    db.commit()
    return {"message": "File deleted successfully"}


def reingest_file(file_id: int, user_id: int, db: Session) -> dict:
    record = db.query(FileRecord).filter(FileRecord.id == file_id).first()
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
    db.commit()
    db.refresh(job)

    result = run_ingestion.delay(job.id, record.id)
    job.celery_task_id = result.id
    db.commit()

    return {"message": "Re-ingestion started", "job_id": job.id}

def get_file_by_user_id(user_id, db):
    
    user_file = db.query(FileRecord).where(FileRecord.user_id == user_id,FileRecord.is_active == True).first();
    return user_file