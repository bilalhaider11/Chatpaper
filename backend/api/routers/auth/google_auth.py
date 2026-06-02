import logging
import secrets
from datetime import timedelta

import httpx
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import create_access_token
from core.config import settings
from core.dependencies import get_db
from core.redis_client import get_redis
from services import auth as service_auth

logger = logging.getLogger(__name__)

_OAUTH_CODE_TTL = 60  # seconds; single-use code exchanged by the frontend

oauth = OAuth()
if settings.google_client_id and settings.google_client_secret:
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
        authorize_params=None,
    )

router = APIRouter(prefix="/auth", tags=["auth"])


def _callback_redirect_uri(request: Request) -> str:
    return str(request.url_for("google_callback"))


@router.get("/google-login")
async def google_login(request: Request):
    if not settings.google_client_id:
        raise HTTPException(status_code=501, detail="Google OAuth is not configured on this server.")
    redirect_uri = _callback_redirect_uri(request)
    request.session["oauth_redirect_uri"] = redirect_uri
    request.session["login_redirect"] = settings.frontend_url
    return await oauth.google.authorize_redirect(
        request,
        redirect_uri,
        prompt="select_account",
    )


@router.get("/google-callback")
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as exc:
        logger.exception("Google token exchange failed")
        raise HTTPException(status_code=401, detail="Google authentication failed.") from exc

    user_info = token.get("userinfo")
    if not user_info and token.get("access_token"):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {token['access_token']}"},
            )
            response.raise_for_status()
            user_info = response.json()

    if not user_info:
        raise HTTPException(status_code=401, detail="Google authentication failed.")

    iss = user_info.get("iss")
    user_email = user_info.get("email")
    if iss not in ("https://accounts.google.com", "accounts.google.com") or not user_email:
        raise HTTPException(status_code=401, detail="Google authentication failed.")

    user_data = await service_auth.get_user_by_email(db, user_email)
    if user_data is None:
        user_data = await service_auth.create_google_user(db, user_email)

    role = user_data.role.value if hasattr(user_data.role, "value") else user_data.role

    access_token = create_access_token(
        data={"id": user_data.id, "email": user_data.email, "role": role},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )

    redis = get_redis()
    if redis is None:
        raise HTTPException(
            status_code=503,
            detail="Auth service temporarily unavailable. Please try again.",
        )

    # Store JWT under a short-lived single-use code so it never appears in the redirect URL.
    code = secrets.token_urlsafe(32)
    await redis.set(f"oauth:code:{code}", access_token, ex=_OAUTH_CODE_TTL)

    frontend_url = request.session.pop("login_redirect", settings.frontend_url) or settings.frontend_url or "/"
    return RedirectResponse(url=f"{frontend_url.rstrip('/')}/login?code={code}")


@router.post("/exchange-token")
async def exchange_oauth_token(code: str = Body(..., embed=True)):
    """Exchange a short-lived OAuth code for a JWT. Codes are single-use and expire in 60 s."""
    redis = get_redis()
    if redis is None:
        raise HTTPException(status_code=503, detail="Auth service temporarily unavailable.")

    # GETDEL atomically reads and deletes — prevents replay attacks.
    access_token = await redis.getdel(f"oauth:code:{code}")
    if access_token is None:
        raise HTTPException(status_code=401, detail="Invalid or expired code.")

    return {"access_token": access_token, "token_type": "bearer"}
