from pydantic import BaseModel, ConfigDict
from datetime import datetime
from models import auth

class UserBase(BaseModel):
	email: str

class UserCreate(UserBase):
	password: str

class UserLogin(UserBase):
	password: str


class User(UserBase):
	id: int
	is_active: bool
	role: auth.UserRole
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

