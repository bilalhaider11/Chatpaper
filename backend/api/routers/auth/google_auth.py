import logging
import secrets
from datetime import timedelta

import httpx
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from core.auth import create_access_token
from core.config import settings
from core.dependencies import get_db
from schema import auth as schema_auth
from services import auth as service_auth

logger = logging.getLogger(__name__)

oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
    authorize_params=None

)

router = APIRouter(prefix="/auth", tags=["auth"])


def _google_callback_url(request: Request) -> str:
    """OAuth redirect URI registered in Google Cloud Console."""
    configured = (settings.redirect_url or "").strip()
    if configured.endswith(""):
        return configured
    if configured:
        return f"{configured.rstrip('/')}"
    return str(request.url_for(""))


@router.get("/google-login")
async def google_login(request: Request):
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=503,
            detail="Google sign-in is not configured (set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET).",
        )

    redirect_uri = _google_callback_url(request)
    request.session["oauth_redirect_uri"] = redirect_uri
    request.session["login_redirect"] = settings.frontend_url
    return await oauth.google.authorize_redirect(
        request,
        redirect_uri,
        prompt="select_account",
    )


@router.get("")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as exc:
        logger.exception("Google token exchange failed")
        raise HTTPException(
            status_code=401,
            detail=f"Google authentication failed: {exc}",
        ) from exc
    
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

    userData = service_auth.get_user_by_email(db, user_email)
    if userData is None:
        new_user = schema_auth.UserCreate(
            email=user_email,
            password="qwQW12!@"
        )
        userData = service_auth.create_new_user(db, new_user)
        

    role = userData.role.value if hasattr(userData.role, "value") else userData.role
    
    access_token = create_access_token(
        data={
            "id": userData.id,
            "email": userData.email,
            "role": role,
        },
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    
    frontend_url = request.session.pop("login_redirect", settings.frontend_url)
    redirect_target = f"{frontend_url.rstrip('/')}/login?token={access_token}"
    return RedirectResponse(url=redirect_target)
