import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.file_model import FileRecord
from models.ingestion import IngestionJob
from tasks.ingestion_tasks import run_ingestion


UPLOAD_DIR = Path(__file__).resolve().parents[4] / "files"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def upload_files(file, db: Session, current_user, description):
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

    job = IngestionJob(file_id=db_record.id, status=IngestionJob.STATUS_QUEUED)
    db.add(job)
    db.commit()
    db.refresh(job)

    result = run_ingestion.delay(job.id, db_record.id)
    job.celery_task_id = result.id
    db.commit()

    return db_record


def delete_file(file_id, db: Session):
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
