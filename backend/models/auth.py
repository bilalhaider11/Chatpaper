from sqlalchemy import Boolean, Column, Integer, String, Enum
from enum import Enum as PythonEnum

from core.database import Base
from core.models import CommonModel


class UserRole(str, PythonEnum):
    user = "user"
    admin = "admin"


class User(CommonModel):
    __tablename__ = "users"

    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)

    role = Column(Enum(UserRole), default=UserRole.user)


