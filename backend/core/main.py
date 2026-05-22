from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from sqladmin import Admin
from core.config import settings
from core.database import engine
from models import auth, file_model
import models.ingestion  # noqa: F401 — registers DocumentParent, IngestionJob with Base
import models.conversation  # noqa: F401 — registers ConversationList, Conversation with Base
from api.router import api_router
from .admin import UserAdmin, authentication_backend
from services.messaging import start_messaging, stop_messaging

@asynccontextmanager
async def lifespan(app: FastAPI):
    _ini = Path(__file__).resolve().parent.parent / "alembic.ini"
    cfg = Config(str(_ini))
    cfg.set_main_option("script_location", str(_ini.parent / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.database)
    command.upgrade(cfg, "head")
    await start_messaging()
    yield
    await stop_messaging()


app = FastAPI(lifespan=lifespan)

# SessionMiddleware is required by sqladmin's AuthenticationBackend.
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, session_cookie="session",same_site="lax",https_only=False)





app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)

# Admin panel — protected by AdminAuth; password hashes are excluded from column_list.
admin = Admin(app, engine, authentication_backend=authentication_backend)
admin.add_view(UserAdmin)


@app.get("/")
async def read_home_page():
    return {"msg": "Initialization done"}
