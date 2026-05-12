from sqlalchemy import Boolean, Column, Integer, String, Enum
from enum import Enum as PythonEnum

from Chatpaper.backend.core.database import Base
from Chatpaper.backend.core.models import CommonModel


class UserRole(str, PythonEnum):
    customer = "customer"
    vendor = "vendor"
    admin = "admin"


class User(CommonModel):
    __tablename__ = "users"

    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)

    role = Column(Enum(UserRole), default=UserRole.customer)


