from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from core.password import hash_password, verify_password
from models.auth import User
from schema import auth as schema_auth


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
    hashed_password = hash_password(user.password)
    new_user = User(
        email=user.email,
        name=user.name,
        password=hashed_password,
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


async def update_user(db: AsyncSession, user_id: int, user: schema_auth.UserUpdate) -> User:
    db_user = await get_user_by_id(db, user_id)
    updated_data = user.model_dump(exclude_unset=True)
    for key, value in updated_data.items():
        setattr(db_user, key, value)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    from core.auth import invalidate_user_cache
    await invalidate_user_cache(user_id)
    return db_user




async def change_own_password(
    db: AsyncSession,
    user: User,
    payload: schema_auth.ChangePassword,
):
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(password=hash_password(payload.new_password))
    )

    await db.commit()

    from core.auth import invalidate_user_cache
    await invalidate_user_cache(user.id)
  
async def change_user_password(
    db: AsyncSession,
    user_id: int,
    payload: schema_auth.ChangePassword,
) -> User:
    db_user = await get_user_by_id(db, user_id)
    db_user.password = hash_password(payload.new_password)

    await db.commit()
    await db.refresh(db_user)
    from core.auth import invalidate_user_cache

    await invalidate_user_cache(user_id)
    return db_user

async def delete_user(db: AsyncSession, user_id: int) -> dict:
    db_user = await get_user_by_id(db, user_id)
    user_data = {"id": db_user.id, "email": db_user.email, "role": db_user.role}
    db.delete(db_user)
    await db.commit()
    from core.auth import invalidate_user_cache
    await invalidate_user_cache(user_id)
    return user_data
