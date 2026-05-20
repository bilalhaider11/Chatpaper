from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from core.database import engine
from sqladmin import Admin
from models import auth, file_model
from api.router import api_router
from core.config import settings
from .admin import UserAdmin
#from fastapi.middleware.cors import CORSMiddleware
#from starlette.requests import Request
from starlette.middleware.sessions import SessionMiddleware
#import uvicorn
#from google.oauth2 import id_token
#from google.auth.transport import requests

app = FastAPI()

app.add_middleware(SessionMiddleware ,secret_key=settings.secret_key, session_cookie="session",same_site="lax",https_only=False)

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

