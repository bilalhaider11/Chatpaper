import json
from datetime import datetime, timezone
import secrets

from fastapi import HTTPException
from passlib.context import CryptContext
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from core.redis_client import get_redis
from models.auth import User
from schema import auth as schema_auth

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class RedisUnavailableError(Exception):
    pass


class LoginCodeInvalidError(Exception):
    pass


LOGIN_CODE_PREFIX = "login_code:"

def _login_code_key(code: str) -> str:
    return f"{LOGIN_CODE_PREFIX}{code}"


async def create_google_login_code(code: str, user: User, ttl_seconds: int) -> None:
    redis_client = get_redis()
    if redis_client is None:
        raise RedisUnavailableError("Redis is unavailable")

    payload = json.dumps({"user_id": user.id, "email": user.email})
    try:
        success = await redis_client.set(_login_code_key(code), payload, ex=ttl_seconds)
    except RedisError as exc:
        raise RedisUnavailableError("Redis error while storing login code") from exc

    if not success:
        raise RedisUnavailableError("Failed to create login code")


async def consume_google_login_code(code: str) -> dict[str, str | int]:
    redis_client = get_redis()
    if redis_client is None:
        raise RedisUnavailableError("Redis is unavailable")

    try:
        payload = await redis_client.getdel(_login_code_key(code))
    except RedisError as exc:
        raise RedisUnavailableError("Redis error while consuming login code") from exc

    if not payload:
        raise LoginCodeInvalidError("Invalid or expired login code")

    try:
        data = json.loads(payload)
        print("Parsed login code data: ", data)
    except json.JSONDecodeError as exc:
        raise LoginCodeInvalidError("Invalid login code payload") from exc

    user_id = data.get("user_id")
    email = data.get("email")
    if not user_id or not email:
        raise LoginCodeInvalidError("Invalid login code payload")

    return {"user_id": user_id, "email": email}


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email, User.is_active == True).first()


def get_user_by_id(db: Session, user_id: int) -> User:
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


def create_new_user(db: Session, user: schema_auth.UserCreate, track_google_login: bool = False) -> User:
    if track_google_login:
        hashed_password = None
    else:
        hashed_password = pwd_context.hash(user.password)
    new_user = User(email=user.email, password=hashed_password, loggedin_by_google=track_google_login)
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
