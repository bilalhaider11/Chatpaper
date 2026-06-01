from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as db:
        yield db


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
