from fastapi import APIRouter

from Chatpaper.backend.api.routers.auth.auth import router as auth_router
from Chatpaper.backend.api.routers.file_handling.files import router as files_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(files_router)
