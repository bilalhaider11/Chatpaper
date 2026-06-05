from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from core.password_validation import validate_password_strength
from models import auth


class UserBase(BaseModel):
    email: EmailStr
    name: str | None = None


class UserCreate(UserBase):
    name: str
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Name cannot be empty.")
        return trimmed


class UserLogin(UserBase):
    password: str


class User(UserBase):
    id: int
    is_active: bool
    role: auth.UserRole
    auth_provider: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    is_active: bool | None = None
    role: auth.UserRole | None = None
    password: str | None = None
    name: str | None = None

class ChangePassword(BaseModel):
    new_password: str = Field(min_length=8)
    user_id: int | None = None

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return validate_password_strength(value)
    


class Token(BaseModel):
    access_token: str
    token_type: str
