from pathlib import Path
from uuid import uuid4
import shutil

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.config import settings
from core.dependencies import get_db
from models.auth import UserRole
from models.file_model import FileRecord
from models.ingestion import IngestionJob
from schema.file import FileRecordResponse, FileRecordUpdate, IngestionStatusResponse
from services import files

router = APIRouter(prefix="/files", tags=["files"])

_MAX_BYTES = settings.max_file_size_mb * 1024 * 1024


@router.post("/upload", response_model=FileRecordResponse)
async def upload_file(
    file: UploadFile = File(...),
    description: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if file.content_type not in settings.allowed_mime_types:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported file type '{file.content_type}'. "
                f"Accepted types: {', '.join(settings.allowed_mime_types)}"
            ),
        )

    # seek to end — tell() gives size without loading the whole file into memory
    await file.seek(0)
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size > _MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {settings.max_file_size_mb} MB.",
        )

    return files.upload_files(file, db, current_user, description)
    
    

@router.get("/", response_model=list[FileRecordResponse])
async def list_files(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    q = db.query(FileRecord).order_by(FileRecord.id.desc())
    if current_user.role != UserRole.admin:
        q = q.filter(FileRecord.user_id == current_user.id)
    return q.all()


@router.get("/{file_id}/ingestion-status", response_model=IngestionStatusResponse)
async def get_ingestion_status(
    file_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    record = db.query(FileRecord).filter(FileRecord.id == file_id).first()
    if record is None or (
        current_user.role != UserRole.admin and record.user_id != current_user.id
    ):
        raise HTTPException(status_code=404, detail="File not found")

    job = (
        db.query(IngestionJob)
        .filter(IngestionJob.file_id == file_id)
        .order_by(IngestionJob.id.desc())
        .first()
    )
    if job is None:
        raise HTTPException(status_code=404, detail="No ingestion job found for this file")
    return job


@router.delete("/{file_id}")
async def delete_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    owner_id = None if current_user.role == UserRole.admin else current_user.id
    return files.delete_file(file_id, owner_id, db)
