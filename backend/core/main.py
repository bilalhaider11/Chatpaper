from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from core.config import settings
from core.database import engine
from sqladmin import Admin
from models import auth, file_model
import models.ingestion  # noqa: F401 — registers DocumentParent, IngestionJob with Base
from api.router import api_router
from .admin import UserAdmin


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ini = Path(__file__).resolve().parent.parent / "alembic.ini"
    cfg = Config(str(_ini))
    cfg.set_main_option("script_location", str(_ini.parent / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.database)
    command.upgrade(cfg, "head")
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)

files_dir = Path(__file__).resolve().parents[2] / "files"
files_dir.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=str(files_dir)), name="files")

# ========== admin =======
admin = Admin(app, engine)
admin.add_view(UserAdmin)


@app.get('/')
async def read_home_page():
    return {"msg": "Initialization done"}

