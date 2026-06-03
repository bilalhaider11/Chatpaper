from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from starlette.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user, require_admin
from core.config import settings
from core.dependencies import get_db
from core.limiter import limiter
from models.auth import User, UserRole
from models.file_model import FileRecord
from models.ingestion import IngestionJob
from schema.file import FileRecordResponse, IngestionStatusResponse, UploadResponse
from services import files

router = APIRouter(prefix="/files", tags=["files"])

_MAX_BYTES = settings.max_file_size_mb * 1024 * 1024


async def _get_owned_file(db: AsyncSession, file_id: int, user: User) -> FileRecord:
    result = await db.execute(select(FileRecord).where(FileRecord.id == file_id))
    record = result.scalars().first()
    if record is None or (
        user.role != UserRole.admin and (record.user_id != user.id or not record.is_active)
    ):
        raise HTTPException(status_code=404, detail="File not found")
    return record


@router.post("/upload", response_model=UploadResponse)
@limiter.limit("10/minute")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    description: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in settings.allowed_mime_types:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported file type '{file.content_type}'. "
                f"Accepted types: {', '.join(settings.allowed_mime_types)}"
            ),
        )

    # Check file size using seek before reading content into memory.
    await file.seek(0)
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size > _MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {settings.max_file_size_mb} MB.",
        )

    # Read first 2 KB to verify actual MIME type via libmagic (prevents Content-Type spoofing).
    first_bytes = await file.read(2048)
    await file.seek(0)

    try:
        import magic
        detected_mime = magic.from_buffer(first_bytes, mime=True)
        if detected_mime not in settings.allowed_mime_types:
            raise HTTPException(
                status_code=415,
                detail=(
                    f"File content detected as '{detected_mime}', which is not permitted. "
                    f"Accepted types: {', '.join(settings.allowed_mime_types)}"
                ),
            )
    except ImportError:
        pass  # python-magic not installed — fall back to header-only check

    return await files.upload_files(file, db, current_user, description)


@router.get("/", response_model=list[FileRecordResponse])
async def list_files(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(FileRecord).order_by(FileRecord.id.desc()).limit(limit).offset(offset)
    if current_user.role != UserRole.admin:
        stmt = stmt.where(FileRecord.user_id == current_user.id, FileRecord.is_active == True)  # noqa: E712
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{file_id}/download")
async def download_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = await _get_owned_file(db, file_id, current_user)

    from services.files import UPLOAD_DIR
    filename_on_disk = Path(record.filepath).name
    disk_path = UPLOAD_DIR / filename_on_disk
    if not disk_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=str(disk_path),
        filename=record.filename,
        media_type=record.file_type or "application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(record.filename)}"},
    )


@router.get("/{file_id}/ingestion-status", response_model=IngestionStatusResponse)
async def get_ingestion_status(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_owned_file(db, file_id, current_user)

    result = await db.execute(
        select(IngestionJob)
        .where(IngestionJob.file_id == file_id)
        .order_by(IngestionJob.id.desc())
        .limit(1)
    )
    job = result.scalars().first()
    if job is None:
        raise HTTPException(status_code=404, detail="No ingestion job found for this file")
    return job


@router.post("/{file_id}/reingest")
async def reingest_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = await _get_owned_file(db, file_id, current_user)
    return await files.reingest_file(file_id, record.user_id, db)


@router.delete("/{file_id}")
async def delete_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    record = await _get_owned_file(db, file_id, current_user)
    return await files.delete_file(file_id, record.user_id, db)
