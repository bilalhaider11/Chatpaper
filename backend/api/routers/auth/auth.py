from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from Chatpaper.backend.core import auth as auth_functions
from Chatpaper.backend.schema import auth as schema_auth
from Chatpaper.backend.core.config import settings
from Chatpaper.backend.core.dependencies import get_db
from Chatpaper.backend.models.check_role import RoleChecker

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=schema_auth.Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    member = auth_functions.authenticate_user(
        db,
        email=form_data.username,
        password=form_data.password,
    )

    if not member:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = auth_functions.create_access_token(
        data={"id": member.id, "email": member.email, "role": member.role},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/users", response_model=schema_auth.User)
async def create_new_user(user: schema_auth.UserCreate, db: Session = Depends(get_db)):
    db_user = auth_functions.get_user_by_email(db, user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="User already exists")
    return auth_functions.create_new_user(db, user)


@router.get(
    "/users",
    response_model=list[schema_auth.User],
    dependencies=[Depends(RoleChecker(["admin"]))],
)
async def read_all_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return auth_functions.read_all_user(db, skip, limit)


@router.get("/users/me", response_model=schema_auth.User)
async def read_me(
    current_user: Annotated[schema_auth.User, Depends(auth_functions.get_current_user)],
):
    return current_user


@router.get(
    "/users/{user_id}",
    response_model=schema_auth.User,
    dependencies=[Depends(RoleChecker(["admin"]))],
)
async def read_user_by_id(user_id: int, db: Session = Depends(get_db)):
    return auth_functions.get_user_by_id(db, user_id)


@router.patch(
    "/users/{user_id}",
    response_model=schema_auth.User,
    dependencies=[Depends(RoleChecker(["admin"]))],
)
async def update_user(
    user_id: int, user: schema_auth.UserUpdate, db: Session = Depends(get_db)
):
    return auth_functions.update_user(db, user_id, user)


@router.delete(
    "/users/{user_id}",
    response_model=schema_auth.User,
    dependencies=[Depends(RoleChecker(["admin"]))],
)
async def delete_user(user_id: int, db: Session = Depends(get_db)):
    return auth_functions.delete_user(db, user_id)
