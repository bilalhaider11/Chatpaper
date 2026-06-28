from sqlalchemy import Boolean, Column, Integer, String, Enum, CheckConstraint
from enum import Enum as PythonEnum

from core.database import Base
from core.models import CommonModel


class UserRole(str, PythonEnum):
    user = "user"
    admin = "admin"


class User(CommonModel):
    __tablename__ = "users"

    email = Column(String, unique=True, index=True, nullable=False)
    name= Column(String, nullable=False)
    password = Column(String, nullable=True)
    auth_provider = Column(String, nullable=False, server_default="password")

    role = Column(Enum(UserRole), default=UserRole.user)
    credits = Column(Integer, nullable=True)
    
    __table_args__ = (
        CheckConstraint('char_length(password) >= 8', name='password_min_length'),
    )


