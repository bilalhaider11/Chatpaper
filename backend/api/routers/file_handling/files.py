from pathlib import Path
from uuid import uuid4
import shutil

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from core.dependencies import get_db
from models.file_model import FileRecord
from models.ingestion import IngestionJob
from schema.file import FileRecordResponse, FileRecordUpdate, IngestionStatusResponse
from core.auth import get_current_user
from services import files

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload", response_model=FileRecordResponse)
async def upload_file(
    file: UploadFile = File(...),
    description: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return files.upload_files(file ,db ,current_user ,description)
    
    

@router.get("/", response_model=list[FileRecordResponse])
async def list_files(
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    return db.query(FileRecord).order_by(FileRecord.id.desc()).all()


@router.get("/{file_id}/ingestion-status", response_model=IngestionStatusResponse)
async def get_ingestion_status(
    file_id: int,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
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
    _current_user=Depends(get_current_user),
):
    return files.delete_file(file_id, db)
