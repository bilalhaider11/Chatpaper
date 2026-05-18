from pydantic import BaseModel, ConfigDict


class FileRecordBase(BaseModel):
    description: str | None = None


class FileRecordUpdate(BaseModel):
    description: str | None = None
    is_active: bool | None = None


class FileRecordResponse(FileRecordBase):
    id: int
    filename: str
    filepath: str
    filesize: int
    is_active: bool
    model_config = ConfigDict(from_attributes=True)
