from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from models import auth


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str

class UserLogin(UserBase):
    auth_provider: str = "password"


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


class Token(BaseModel):
    access_token: str
    token_type: str
    

class GoogleCodeExchange(BaseModel):
    code: str
