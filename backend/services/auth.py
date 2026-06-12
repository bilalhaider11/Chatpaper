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
from fastapi import FastAPI
from fastapi_mail import FastMail, MessageSchema
from core.email_config import configure_email_credentials

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

async def get_ui(reset_password_link: str):
    subject = "Reset Your Chatpaper Password"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Reset Your Password</title>
    </head>
    <body style="
        margin:0;
        padding:0;
        background-color:#f4f7fb;
        font-family:Arial, Helvetica, sans-serif;
        color:#333333;
    ">
        <table width="100%" cellpadding="0" cellspacing="0" style="padding:40px 0;">
            <tr>
                <td align="center">

                    <table width="600" cellpadding="0" cellspacing="0"
                        style="
                            background:#ffffff;
                            border-radius:12px;
                            overflow:hidden;
                            box-shadow:0 2px 12px rgba(0,0,0,0.08);
                        ">

                        <!-- Header -->
                        <tr>
                            <td align="center"
                                style="
                                    background:#111827;
                                    color:#ffffff;
                                    padding:32px;
                                    font-size:28px;
                                    font-weight:bold;
                                ">
                                Chatpaper
                            </td>
                        </tr>

                        <!-- Body -->
                        <tr>
                            <td style="padding:40px;">

                                <h2 style="
                                    margin-top:0;
                                    color:#111827;
                                ">
                                    Reset Your Password
                                </h2>

                                <p style="
                                    font-size:16px;
                                    line-height:1.7;
                                    color:#4b5563;
                                ">
                                    We received a request to reset the password
                                    associated with your Chatpaper account.
                                </p>

                                <p style="
                                    font-size:16px;
                                    line-height:1.7;
                                    color:#4b5563;
                                ">
                                    Click the button below to create a new password.
                                </p>

                                <div style="text-align:center; margin:35px 0;">
                                    <a href="{reset_password_link}"
                                       style="
                                            background:#2563eb;
                                            color:#ffffff;
                                            text-decoration:none;
                                            padding:14px 32px;
                                            border-radius:8px;
                                            font-size:16px;
                                            font-weight:600;
                                            display:inline-block;
                                       ">
                                        Reset Password
                                    </a>
                                </div>

                                <p style="
                                    font-size:14px;
                                    color:#6b7280;
                                    line-height:1.7;
                                ">
                                    This password reset link will expire automatically
                                    for security reasons.
                                </p>

                                <p style="
                                    font-size:14px;
                                    color:#6b7280;
                                    line-height:1.7;
                                ">
                                    If you did not request a password reset,
                                    you can safely ignore this email.
                                    No changes will be made to your account.
                                </p>

                                <hr style="
                                    border:none;
                                    border-top:1px solid #e5e7eb;
                                    margin:30px 0;
                                ">

                            </td>
                        </tr>

                        <!-- Footer -->
                        <tr>
                            <td
                                style="
                                    background:#f9fafb;
                                    padding:24px;
                                    text-align:center;
                                    color:#6b7280;
                                    font-size:12px;
                                "
                            >
                                © 2026 Chatpaper. All rights reserved.
                                <br>
                                Secure AI-powered document analysis and research platform.
                            </td>
                        </tr>

                    </table>

                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    return subject, html_content


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
    
    url = reset_url.format(token=token)
    subject,email_format = await get_ui(url)
    conf = configure_email_credentials()
    
    message = MessageSchema(
       subject=subject,
       recipients=[user.email],
       body=email_format,
       subtype="html"
    )
    try:
        fm = FastMail(conf)
        await fm.send_message(message)
    except Exception as e:
        raise
        

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
