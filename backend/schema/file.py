from datetime import datetime

from pydantic import BaseModel, ConfigDict, computed_field


class FileRecordBase(BaseModel):
    description: str | None = None


class FileRecordUpdate(BaseModel):
    description: str | None = None
    is_active: bool | None = None


class FileRecordResponse(FileRecordBase):
    id: int
    filename: str
    filesize: int
    is_active: bool
    ingestion_status: str | None = None
    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def download_url(self) -> str:
        return f"/files/{self.id}/download"


class IngestionStatusResponse(BaseModel):
    id: int
    file_id: int
    status: str
    current_stage: int | None
    total_stages: int
    error_message: str | None
    error_type: str | None
    completed_at: datetime | None
    model_config = ConfigDict(from_attributes=True)
