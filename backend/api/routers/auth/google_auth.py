# auth.py
import requests
from sqlalchemy.orm import Session
from core.auth import create_access_token
from fastapi import FastAPI, Depends, HTTPException, status, Request, Cookie, APIRouter
from fastapi.responses import JSONResponse, RedirectResponse
from authlib.integrations.starlette_client import OAuth
from core.config import settings
from starlette.middleware.sessions import SessionMiddleware
from datetime import datetime, timedelta
from jose import jwt, ExpiredSignatureError, JWTError
from dotenv import load_dotenv
from services import auth as service_auth
import os
import uuid
from schema import auth as schema_auth
import traceback
from core.dependencies import get_db


# Load environment variables
load_dotenv(override=True)

# App Configuration
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY"))

# OAuth Setup
oauth = OAuth()
oauth.register(
    name="auth_demo",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    authorize_url="https://accounts.google.com/o/oauth2/auth",
    authorize_params=None,
    access_token_url="https://accounts.google.com/o/oauth2/token",
    access_token_params=None,
    refresh_token_url=None,
    authorize_state=settings.secret_key,
    redirect_uri="http://127.0.0.1:3000/login",
    jwks_uri="https://www.googleapis.com/oauth2/v3/certs",
    client_kwargs={"scope": "openid profile email"},
)

# JWT Configurations
SECRET_KEY = settings.jwt_secret_key
ALGORITHM = settings.algorithm


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/google-login")
async def login(request: Request):
    request.session.clear()
    referer = request.headers.get("referer")
    frontend_url = os.getenv("FRONTEND_URL")
    redirect_url = os.getenv("REDIRECT_URL")
    print("..............................................................................................")
    print("referer: ",referer)
    
    request.session["login_redirect"] = frontend_url 
    

    response = await oauth.auth_demo.authorize_redirect(request, redirect_url, prompt="consent")
    print("response: ",response)
    return response


@router.get("")
async def auth(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.auth_demo.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=401, detail="Google authentication failed.")

    try:
        user_info_endpoint = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {"Authorization": f'Bearer {token["access_token"]}'}
        print("headers: ",headers)
        google_response = requests.get(user_info_endpoint, headers=headers)
        user_info = google_response.json()
    except Exception as e:
        raise HTTPException(status_code=401, detail="Google authentication failed.")

    user = token.get("userinfo")
    expires_in = token.get("expires_in")
    user_id = user.get("sub")
    iss = user.get("iss")
    user_email = user.get("email")

    if iss not in ["https://accounts.google.com", "accounts.google.com"]:
        raise HTTPException(status_code=401, detail="Google authentication failed.")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Google authentication failed.")
    # Create JWT token
    access_token_expires = timedelta(seconds=expires_in)
    access_token = create_access_token(data={"sub": user_id, "email": user_email}, expires_delta=access_token_expires)
    
    userData = service_auth.get_user_by_email(db, user_email)
    if userData is None:
        new_user = schema_auth.UserCreate(
            email=user_email,
            password="qwQW12!@"
        )
        userData = service_auth.create_new_user(db, new_user)
    
    session_id = str(uuid.uuid4())

    redirect_url = request.session.pop("login_redirect", "")
    response = RedirectResponse(redirect_url)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,  # Ensure you're using HTTPS
        samesite="strict",  # Set the SameSite attribute to None
    )

    return response
