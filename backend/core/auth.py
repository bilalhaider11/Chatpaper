import json
from datetime import datetime, timedelta, timezone
from typing import Annotated
from core.password import verify_password
from fastapi import Depends, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from core import dependencies
from core.config import settings
from models.auth import User, UserRole
from services import auth

_USER_CACHE_TTL = settings.access_token_expire_minutes * 60


async def _get_cached_user(user_id: int) -> User | None:
    from core.redis_client import get_redis
    redis = get_redis()
    if redis is None:
        return None
    raw = await redis.get(f"user:cache:{user_id}")
    if raw is None:
        return None
    data = json.loads(raw)
    user = User()
    user.id = data["id"]
    user.email = data["email"]
    user.name = data.get("name")
    user.role = data["role"]
    user.is_active = data["is_active"]
    user.auth_provider = data["auth_provider"]
    from datetime import datetime
    # Old cache entries lack these fields; fall through to DB to rebuild them.
    if not data.get("created_at") or not data.get("updated_at"):
        return None
    user.created_at = datetime.fromisoformat(data["created_at"])
    user.updated_at = datetime.fromisoformat(data["updated_at"])
    return user


async def _cache_user(user: User) -> None:
    from core.redis_client import get_redis
    redis = get_redis()
    if redis is None:
        return
    data = {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role.value if hasattr(user.role, "value") else user.role,
        "is_active": user.is_active,
        "auth_provider": user.auth_provider,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }
    await redis.set(f"user:cache:{user.id}", json.dumps(data), ex=_USER_CACHE_TTL)


async def invalidate_user_cache(user_id: int) -> None:
    from core.redis_client import get_redis
    redis = get_redis()
    if redis is not None:
        await redis.delete(f"user:cache:{user_id}")


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | bool:
    member = await auth.get_user_by_email(db, email)
    if not member:
        return False
    if not verify_password(password, member.password):
        return False
    return member


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


async def get_current_user(
    token: Annotated[str, Depends(dependencies.oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(dependencies.get_db)],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: int | None = payload.get("id")
        current_email: str | None = payload.get("email")
        if current_email is None:
            raise credentials_exception

        # Fast path: return cached user row without hitting the DB.
        if user_id is not None:
            cached = await _get_cached_user(user_id)
            if cached is not None:
                if not cached.is_active:
                    raise credentials_exception
                return cached

        user = await auth.get_user_by_email(db, current_email)
        if user is None:
            raise credentials_exception

        await _cache_user(user)
        return user
    except JWTError:
        raise credentials_exception


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return current_user
