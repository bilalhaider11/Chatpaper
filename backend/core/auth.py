from fastapi import HTTPException, status, Depends
from sqlalchemy.orm import Session
from Chatpaper.backend.models.auth import UserRole, User
from Chatpaper.backend.schema import auth as schema_auth
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from typing import Annotated
from Chatpaper.backend.services import auth
from Chatpaper.backend.core.config import settings
from Chatpaper.backend.core import dependencies

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# =====================> login/logout <============================
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def authenticate_user(db: Session, email: str, password: str):
    member = auth.get_user_by_email(db, email)
    if not member:
        return False
    if not verify_password(password, member.password):
        return False
    return member

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt

# get current users info 
def get_current_user(token: Annotated[str, Depends(dependencies.oauth2_scheme)], db: Annotated[Session, Depends(dependencies.get_db)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        current_email: str = payload.get("email")
        if current_email is None:
            raise credentials_exception
        user = auth.get_user_by_email(db, current_email)
        if user is None:
            raise credentials_exception
        
        return user
    except JWTError:
        raise credentials_exception
