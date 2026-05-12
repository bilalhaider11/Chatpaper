from fastapi import HTTPException, status, Depends
from sqlalchemy.orm import Session
from models.auth import UserRole, User
from schema import auth as schema_auth
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from typing import Annotated

from core.config import settings
from core import dependencies

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# get user by email 
def get_user_by_email(db: Session, email: str):
    query = db.query(User).filter(User.email == email,User.is_active == True).first()
    return query

# get user by id
def get_user_by_id(db: Session, user_id: int):
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

# crete new user 
def create_new_user(db: Session, user:schema_auth.UserCreate):
    hashed_password = pwd_context.hash(user.password)
    new_user = User(email=user.email, password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

# get all user 
def read_all_user(db: Session, skip: int, limit: int):
    query =  db.query(User).offset(skip).limit(limit).all()
    return query

# update user
def update_user(db: Session, user_id: int, user: schema_auth.UserUpdate):
    db_user = get_user_by_id(db, user_id)
    updated_data = user.model_dump(exclude_unset=True) # partial update
    for key, value in updated_data.items():
        if key == "password":
            value = pwd_context.hash(value)
        setattr(db_user, key, value)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# delete user
def delete_user(db: Session, user_id: int):
    db_user = get_user_by_id(db, user_id)
    db.delete(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user
