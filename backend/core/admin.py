from sqladmin import ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from core.config import settings
from core.redis_client import get_redis
from models.auth import User

_MAX_ADMIN_FAILS = 10
_LOCKOUT_SECONDS = 300  # 5-minute window


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username", "")
        password = form.get("password", "")

        ip = request.client.host if request.client else "unknown"
        redis = get_redis()
        fail_key = f"admin:login:fail:{ip}"

        if redis is not None:
            fails = await redis.get(fail_key)
            if fails and int(fails) >= _MAX_ADMIN_FAILS:
                return False

        if username == settings.admin_username and password == settings.admin_password:
            if redis is not None:
                await redis.delete(fail_key)
            request.session.update({"admin_authenticated": True})
            return True

        if redis is not None:
            pipe = redis.pipeline()
            await pipe.incr(fail_key)
            await pipe.expire(fail_key, _LOCKOUT_SECONDS)
            await pipe.execute()
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return bool(request.session.get("admin_authenticated"))


authentication_backend = AdminAuth(secret_key=settings.secret_key)


class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.email, User.role, User.is_active, User.created_at, User.updated_at]
