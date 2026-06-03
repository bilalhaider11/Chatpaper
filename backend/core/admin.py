import hmac

from sqladmin import ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from core.config import settings
from core.redis_client import get_redis
from models.auth import User

_MAX_ADMIN_FAILS = 10
_LOCKOUT_SECONDS = 300  # 5-minute window

# Atomically increment a counter and set TTL only on the first increment.
_INCR_WITH_EXPIRY = (
    "local v=redis.call('INCR',KEYS[1]) "
    "if v==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end "
    "return v"
)


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username", "")
        password = form.get("password", "")

        ip = request.client.host if request.client else "unknown"
        redis = get_redis()

        # Fail-closed: without Redis the brute-force counter can't be maintained.
        if redis is None:
            return False

        fail_key = f"admin:login:fail:{ip}"
        fails = await redis.get(fail_key)
        if fails and int(fails) >= _MAX_ADMIN_FAILS:
            return False

        # Always evaluate both comparisons — `and` short-circuits and re-introduces the oracle.
        username_ok = hmac.compare_digest(username, settings.admin_username)
        password_ok = hmac.compare_digest(password, settings.admin_password)
        valid = username_ok and password_ok

        if valid:
            await redis.delete(fail_key)
            request.session.update({"admin_authenticated": True})
            return True

        # Atomic INCR + EXPIRE-on-first so the 5-minute window is fixed, not sliding.
        await redis.eval(_INCR_WITH_EXPIRY, 1, fail_key, _LOCKOUT_SECONDS)
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return bool(request.session.get("admin_authenticated"))


authentication_backend = AdminAuth(secret_key=settings.secret_key)


class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.email, User.role, User.is_active, User.created_at, User.updated_at]
