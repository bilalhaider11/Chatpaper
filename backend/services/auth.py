from fastapi import HTTPException
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from models.auth import User
from schema import auth as schema_auth

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email, User.is_active == True).first()


def get_user_by_id(db: Session, user_id: int) -> User:
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


def create_new_user(db: Session, user: schema_auth.UserCreate) -> User:
    hashed_password = pwd_context.hash(user.password)
    new_user = User(email=user.email, password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


def read_all_user(db: Session, skip: int, limit: int) -> list[User]:
    return db.query(User).offset(skip).limit(limit).all()


def update_user(db: Session, user_id: int, user: schema_auth.UserUpdate) -> User:
    db_user = get_user_by_id(db, user_id)
    updated_data = user.model_dump(exclude_unset=True)
    for key, value in updated_data.items():
        if key == "password":
            value = pwd_context.hash(value)
        setattr(db_user, key, value)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def delete_user(db: Session, user_id: int) -> dict:
    db_user = get_user_by_id(db, user_id)
    user_data = {"id": db_user.id, "email": db_user.email, "role": db_user.role}
    db.delete(db_user)
    db.commit()
    return user_data
