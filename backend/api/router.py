from fastapi import APIRouter

from api.routers.auth.auth import router as auth_router
from api.routers.auth.google_auth import router as google_router
from api.routers.file_handling.files import router as files_router
from api.routers.conversation import router as conversation_router

api_router = APIRouter(prefix="/api")

api_router.include_router(auth_router)
api_router.include_router(files_router)
api_router.include_router(conversation_router)
api_router.include_router(google_router)