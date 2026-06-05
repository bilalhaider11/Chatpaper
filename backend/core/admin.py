import hmac

from sqladmin import ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from core.config import settings
from core.redis_client import get_redis
from models.auth import User
from models.conversation import Conversation, ConversationList
from models.file_model import FileRecord
from models.ingestion import DocumentParent, IngestionJob

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
    column_searchable_list = [User.email]
    column_sortable_list = [User.id, User.created_at, User.role]


class FileAdmin(ModelView, model=FileRecord):
    column_list = [
        FileRecord.id, FileRecord.user_id, FileRecord.filename, FileRecord.file_type,
        FileRecord.filesize, FileRecord.ingestion_status, FileRecord.is_active,
        FileRecord.total_pages, FileRecord.uploaded_at,
    ]
    column_searchable_list = [FileRecord.filename]
    column_sortable_list = [FileRecord.id, FileRecord.uploaded_at, FileRecord.ingestion_status]
    # Exclude raw file path from list to avoid accidental exposure
    column_details_exclude_list = [FileRecord.filepath]


class IngestionJobAdmin(ModelView, model=IngestionJob):
    column_list = [
        IngestionJob.id, IngestionJob.file_id, IngestionJob.status,
        IngestionJob.current_stage, IngestionJob.total_stages,
        IngestionJob.retry_count, IngestionJob.error_type,
        IngestionJob.started_at, IngestionJob.completed_at,
    ]
    column_sortable_list = [IngestionJob.id, IngestionJob.status, IngestionJob.started_at]
    column_details_exclude_list = [IngestionJob.error_message]  # shown in detail view only


class ConversationListAdmin(ModelView, model=ConversationList):
    name = "Conversation"
    name_plural = "Conversations"
    column_list = [
        ConversationList.id, ConversationList.user_id, ConversationList.conversation_title,
        ConversationList.conversation_type, ConversationList.file_id,
        ConversationList.is_active, ConversationList.created_at,
    ]
    column_searchable_list = [ConversationList.conversation_title]
    column_sortable_list = [ConversationList.id, ConversationList.created_at, ConversationList.conversation_type]


class MessageAdmin(ModelView, model=Conversation):
    name = "Message"
    name_plural = "Messages"
    column_list = [
        Conversation.id, Conversation.chat_id, Conversation.user_type,
        Conversation.statement, Conversation.created_at,
    ]
    column_sortable_list = [Conversation.id, Conversation.created_at, Conversation.user_type]
