from pathlib import Path
from uuid import uuid4
import shutil

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from Chatpaper.backend.core.dependencies import get_db
from Chatpaper.backend.models.file_model import FileRecord


UPLOAD_DIR = Path(__file__).resolve().parents[4] / "files"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def upload_files(file ,db ,current_user ,description):
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
    )
    
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    
    return db_record
    
    
def delete_file(file_id ,db):
    
    record = db.query(FileRecord).filter(FileRecord.id == file_id).first()
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")

    filename_on_disk = Path(record.filepath).name
    disk_path = UPLOAD_DIR / filename_on_disk
    if disk_path.exists():
        disk_path.unlink()

    db.delete(record)
    db.commit()
    return {"message": "File deleted successfully"}
