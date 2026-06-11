from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from core.password import hash_password, verify_password
from models.auth import User
from schema import auth as schema_auth
from core.config import settings
from fastapi.responses import HTMLResponse
import secrets
from core.redis_client import get_redis    

async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User).where(User.email == email, User.is_active == True)  # noqa: E712
    )
    return result.scalars().first()


async def get_user_by_id(db: AsyncSession, user_id: int) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def create_new_user(db: AsyncSession, user: schema_auth.UserCreate) -> User:
    new_user = User(
        email=user.email,
        password=hash_password(user.password),
        name=user.name,
        auth_provider="password",
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


async def create_google_user(db: AsyncSession, email: str, name: str | None = None) -> User:
    new_user = User(email=email, name=name, password=None, auth_provider="google")
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


async def read_all_user(db: AsyncSession, skip: int, limit: int) -> list[User]:
    result = await db.execute(select(User).offset(skip).limit(limit))
    return list(result.scalars().all())


async def change_password(
    db: AsyncSession,
    current_user: User,
    payload: schema_auth.ChangePassword,
) -> None:
    target_user_id = payload.user_id if payload.user_id is not None else current_user.id

    db_user = await get_user_by_id(db, target_user_id)

    if target_user_id != current_user.id:
        role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
        if role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Not authorized to change this user's password",
            )
    elif db_user.auth_provider != "google":
        if not payload.current_password:
            raise HTTPException(status_code=400, detail="Current password is required")
        if not db_user.password or not verify_password(payload.current_password, db_user.password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")

    update_values: dict = {"password": hash_password(payload.new_password)}
    if db_user.auth_provider == "google":
        update_values["auth_provider"] = "password" 

    await db.execute(
        update(User)
        .where(User.id == target_user_id)
        .values(**update_values)
    )
    await db.commit()

    from core.auth import invalidate_user_cache
    await invalidate_user_cache(target_user_id)

async def update_name(
    db: AsyncSession,
    current_user: User,
    payload: schema_auth.UpdateName,
) -> User:
    target_user_id = payload.user_id if payload.user_id is not None else current_user.id

    if target_user_id != current_user.id:
        role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
        if role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Not authorized to update this user's name",
            )

    db_user = await get_user_by_id(db, target_user_id)
    
    db_user.name = payload.name
    await db.commit()
    await db.refresh(db_user)

    from core.auth import invalidate_user_cache
    await invalidate_user_cache(target_user_id)
    return db_user

async def get_ui(reset_password_link):
    subject="Reset Password request by chatpaper"
    html_content = f"""
    <html>
        <head>
            <title>Reset password link for Chatpaper</title>
        </head>
        <body>
            <h1>Click the link below to reset your password for your email</h1>
            
            <a href="{reset_password_link}">Reset Password</a>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content,subject=subject, status_code=200)

async def request_password_reset(db: AsyncSession, reset_url: str, user: object) -> None:
    """send email logic function."""

    redis = get_redis()
    if redis is None:
        raise HTTPException(
            status_code=503,
            detail="Auth service temporarily unavailable. Please try again.",
        )

    token = secrets.token_urlsafe(32)
    ttl_seconds = settings.email_token_ttl_in_seconds
    await redis.set(f"password_reset:{token}", int(user.id), ex=ttl_seconds)
    
  
    #email_format = await get_ui( reset_url.format(token=token))
    

async def validate_password_reset_token(token: str) -> bool:
    from core.redis_client import get_redis

    redis = get_redis()
    if redis is None:
        raise HTTPException(
            status_code=503,
            detail="Auth service temporarily unavailable. Please try again.",
        )
    return await redis.exists(f"password_reset:{token}") == 1


async def reset_password_with_token(
    db: AsyncSession,
    token: str,
    new_password: str,
) -> User:

    redis = get_redis()
    if redis is None:
        raise HTTPException(
            status_code=503,
            detail="Auth service temporarily unavailable. Please try again.",
        )

    user_id_raw = await redis.getdel(f"password_reset:{token}")
    if user_id_raw is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link.")

    user_id = int(user_id_raw)
    db_user = await get_user_by_id(db, user_id)

    update_values: dict = {"password": hash_password(new_password)}
    if db_user.auth_provider == "google":
        update_values["auth_provider"] = "password"

    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(**update_values)
    )
    await db.commit()
    await db.refresh(db_user)
    from core.auth import _cache_user, invalidate_user_cache


    await invalidate_user_cache(user_id)
    await _cache_user(db_user)
    return db_user


async def delete_user(db: AsyncSession, user_id: int) -> dict:
    db_user = await get_user_by_id(db, user_id)
    user_data = {"id": db_user.id, "email": db_user.email, "role": db_user.role}
    db.delete(db_user)
    await db.commit()
    from core.auth import invalidate_user_cache
    await invalidate_user_cache(user_id)
    return user_data
