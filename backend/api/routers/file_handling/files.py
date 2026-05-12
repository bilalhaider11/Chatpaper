from pathlib import Path
from uuid import uuid4
import shutil

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from core.dependencies import get_db
from models.file_model import FileRecord
from schema.file import FileRecordResponse, FileRecordUpdate
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


@router.delete("/{file_id}")
async def delete_file(
    file_id: int,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    
    return files.delete_file(file_id, db)
    