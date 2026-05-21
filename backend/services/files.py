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
from models.file_model import FileRecord
from models.ingestion import IngestionJob
from tasks.ingestion_tasks import run_ingestion

logger = logging.getLogger(__name__)

# Prefer UPLOAD_DIR env var; fall back to project-relative "files/" directory.
_DEFAULT_UPLOAD_DIR = Path(__file__).resolve().parents[4] / "files"
UPLOAD_DIR = Path(settings.upload_dir) if settings.upload_dir else _DEFAULT_UPLOAD_DIR
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_TERMINAL_STATUSES = {IngestionJob.STATUS_COMPLETE, IngestionJob.STATUS_FAILED_PERMANENT}


def upload_files(file: UploadFile, db: Session, current_user: User, description: str | None) -> FileRecord:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected")

    generated_name = f"{uuid4().hex}_{file.filename}"
    saved_path = UPLOAD_DIR / generated_name

    with saved_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    db_record = FileRecord(
        user_id=current_user.id,
        filename=file.filename,
        filepath=f"/files/{generated_name}",
        file_type=file.content_type,
        filesize=saved_path.stat().st_size,
        description=description,
        ingestion_status=IngestionJob.STATUS_QUEUED,
    )
    db.add(db_record)
    db.commit()
    db.refresh(db_record)

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
        return db_record

    try:
        job = IngestionJob(file_id=db_record.id, status=IngestionJob.STATUS_QUEUED)
        db.add(job)
        db.commit()
        db.refresh(job)
    except IntegrityError:
        db.rollback()
        logger.warning("IntegrityError creating IngestionJob for file %s; duplicate guard hit.", db_record.id)
        return db_record

    result = run_ingestion.delay(job.id, db_record.id)
    job.celery_task_id = result.id
    db.commit()

    return db_record


def delete_file(file_id: int, user_id: int | None, db: Session) -> dict:
    record = db.query(FileRecord).filter(FileRecord.id == file_id).first()
    if record is None or (user_id is not None and record.user_id != user_id):
        raise HTTPException(status_code=404, detail="File not found")

    # CASCADE cleans up postgres rows but chroma vectors need a manual delete
    try:
        delete_vectors_for_file(file_id)
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
