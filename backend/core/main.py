import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware
from sqladmin import Admin
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from core.config import settings
from core.database import engine
from core.limiter import limiter
from models import auth, file_model
from core.redis_client import stop_redis,start_redis
import models.ingestion  # noqa: F401 — registers DocumentParent, IngestionJob with Base
import models.conversation  # noqa: F401 — registers ConversationList, Conversation with Base
from api.router import api_router
from .admin import (
    UserAdmin, FileAdmin, IngestionJobAdmin,
    ConversationListAdmin, MessageAdmin, authentication_backend,
)
from services.messaging import start_messaging, stop_messaging
from services.credits_sync import start_credits_sync, stop_credits_sync

@asynccontextmanager
async def lifespan(app: FastAPI):
    _ini = Path(__file__).resolve().parent.parent / "alembic.ini"
    cfg = Config(str(_ini))
    cfg.set_main_option("script_location", str(_ini.parent / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.database)
    if settings.run_migrations_on_startup:
        await asyncio.to_thread(command.upgrade, cfg, "head")
    await start_redis()
    await start_messaging()
    await start_credits_sync()
    yield
    await stop_credits_sync()
    await stop_messaging()
    await stop_redis()


app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

if settings.trust_proxy_headers:
    _trusted = (
        settings.trusted_proxy_ips
        if settings.trusted_proxy_ips == "*"
        else [ip.strip() for ip in settings.trusted_proxy_ips.split(",") if ip.strip()]
    )
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=_trusted)

# SessionMiddleware is required by sqladmin's AuthenticationBackend.
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, session_cookie="session", same_site="lax", https_only=settings.session_https_only)





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
admin.add_view(FileAdmin)
admin.add_view(IngestionJobAdmin)
admin.add_view(ConversationListAdmin)
admin.add_view(MessageAdmin)


@app.get("/")
async def read_home_page():
    return {"msg": "Initialization done"}
