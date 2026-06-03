import json
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.conversation import Conversation, ConversationList
from models.file_model import FileRecord
from core.config import settings
from schema.conversation import ConversationPageResponse, ConversationResponse
from services.chat_cache import get_active_streams, get_pending_messages


async def _get_owned_file_for_user(db: AsyncSession, file_id: int, user_id: int) -> FileRecord:
    result = await db.execute(
        select(FileRecord).where(
            FileRecord.id == file_id,
            FileRecord.user_id == user_id,
            FileRecord.is_active == True,  # noqa: E712
        )
    )
    record = result.scalars().first()
    if record is None:
        raise HTTPException(
            status_code=400,
            detail="A valid uploaded file is required to start a conversation.",
        )
    return record


async def create_conversation_list(current_user, db: AsyncSession, file_id: int):
    file_record = await _get_owned_file_for_user(db, file_id, current_user.id)

    title = file_record.filename
    if len(title) > 150:
        title = title[:147] + "..."

    db_data = ConversationList(
        user_id=current_user.id,
        file_id=file_record.id,
        conversation_title=title,
        is_active=True,
    )
    db.add(db_data)
    await db.commit()
    await db.refresh(db_data)

    return db_data


async def delete_conversation(convo_id: int, db: AsyncSession) -> dict:
    result = await db.execute(select(ConversationList).where(ConversationList.id == convo_id))
    convo = result.scalars().first()
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if convo.conversation_type == "per_file" and convo.file_id is not None:
        fr = await db.execute(select(FileRecord).where(FileRecord.id == convo.file_id))
        file_record = fr.scalars().first()
        if file_record is not None:
            file_record.is_active = False

    convo.is_active = False
    await db.commit()
    return {"message": "Conversation deleted successfully"}


async def update_conversation_title(title: str, conversation_id: int, user_id: int, session: AsyncSession) -> dict:
    if not title or not title.strip():
        raise HTTPException(status_code=400, detail="No title to update")

    stmt = (
        update(ConversationList)
        .where(ConversationList.id == conversation_id, ConversationList.user_id == user_id)
        .values(conversation_title=title.strip())
    )
    await session.execute(stmt)
    await session.commit()
    return {"Title": "Updated Successfully"}


def _history_cache_key(chat_list_id: int) -> str:
    return f"chat:history:{chat_list_id}"


def _conversation_row_to_message(row: Conversation) -> dict:
    return {
        "id": row.id,
        "chat_id": row.chat_id,
        "temp_id": None,
        "created_at": row.created_at,
        "user_type": row.user_type,
        "statement": row.statement,
        "streaming": False,
    }


def _message_to_cache_row(msg: dict) -> dict:
    created_at = msg.get("created_at")
    return {
        "id": msg["id"],
        "chat_id": msg["chat_id"],
        "user_type": msg["user_type"],
        "statement": msg["statement"],
        "created_at": created_at.isoformat()
        if isinstance(created_at, datetime)
        else created_at,
    }


def _cache_row_to_message(row: dict) -> dict:
    return {
        "id": row["id"],
        "chat_id": row["chat_id"],
        "temp_id": None,
        "created_at": datetime.fromisoformat(row["created_at"])
        if row.get("created_at")
        else None,
        "user_type": row["user_type"],
        "statement": row["statement"],
        "streaming": False,
    }


def _message_sort_ts(m: dict) -> float:
    created_at = m.get("created_at")
    if created_at is None:
        return float("-inf")
    if isinstance(created_at, datetime):
        if created_at.tzinfo is None:
            return created_at.replace(tzinfo=timezone.utc).timestamp()
        return created_at.timestamp()
    return datetime.fromisoformat(str(created_at)).timestamp()


def _sort_messages_asc(messages: list[dict]) -> list[dict]:
    return sorted(messages, key=lambda m: (_message_sort_ts(m), m.get("id") or 0))


def _dedupe_messages_by_id(messages: list[dict]) -> list[dict]:
    seen_ids: set[int] = set()
    deduped: list[dict] = []
    for msg in messages:
        msg_id = msg.get("id")
        if msg_id is not None:
            if msg_id in seen_ids:
                continue
            seen_ids.add(msg_id)
        deduped.append(msg)
    return deduped


def _merge_messages_asc(existing: list[dict], incoming: list[dict]) -> list[dict]:
    return _sort_messages_asc(_dedupe_messages_by_id(existing + incoming))


async def _load_cached_history_rows(redis_client, chat_list_id: int) -> list[dict]:
    cached = await redis_client.get(_history_cache_key(chat_list_id))
    if not cached:
        return []
    return json.loads(cached)


async def _save_cached_history_rows(
    redis_client, chat_list_id: int, rows: list[dict]
) -> None:
    await redis_client.set(
        _history_cache_key(chat_list_id),
        json.dumps(rows),
        ex=settings.chat_data_ttl_seconds,
    )


async def _has_older_messages(db: AsyncSession, chat_list_id: int, oldest_id: int) -> bool:
    result = await db.execute(
        select(Conversation.id)
        .where(
            Conversation.chat_id == chat_list_id,
            Conversation.id < oldest_id,
        )
        .limit(1)
    )
    return result.scalars().first() is not None


def _pending_to_message(msg) -> dict:
    created_at = None
    if msg.enqueued_at:
        try:
            created_at = datetime.fromisoformat(msg.enqueued_at)
        except ValueError:
            created_at = None
    return {
        "id": None,
        "chat_id": msg.chat_id,
        "temp_id": msg.temp_id,
        "created_at": created_at,
        "user_type": msg.user_type,
        "statement": msg.statement,
        "streaming": False,
    }


def _stream_to_message(chat_list_id: int, stream: dict) -> dict:
    created_at = None
    raw_created = stream.get("created_at")
    if raw_created:
        try:
            created_at = datetime.fromisoformat(raw_created)
        except ValueError:
            created_at = None
    return {
        "id": None,
        "chat_id": chat_list_id,
        "temp_id": stream.get("temp_id"),
        "created_at": created_at,
        "user_type": stream.get("user_type", "assistant"),
        "statement": stream["statement"],
        "streaming": bool(stream.get("streaming", True)),
    }


async def get_conversations(
    chat_list_id: int,
    db: AsyncSession,
    limit: int = 25,
    cursor_id: int | None = None,
) -> ConversationPageResponse:
    if not chat_list_id:
        raise HTTPException(status_code=400, detail="Chat does not exist")

    stmt = select(Conversation).where(Conversation.chat_id == chat_list_id)
    if cursor_id is not None:
        stmt = stmt.where(Conversation.id < cursor_id)

    stmt = stmt.order_by(Conversation.created_at.desc(), Conversation.id.desc()).limit(limit)
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    rows.reverse()

    messages = [_conversation_row_to_message(row) for row in rows]

    if cursor_id is None:
        pending = await get_pending_messages(chat_list_id)
        streams = await get_active_streams(chat_list_id)
        for msg in pending:
            messages.append(_pending_to_message(msg))
        for stream in streams:
            messages.append(_stream_to_message(chat_list_id, stream))
        messages = _sort_messages_asc(messages)

    next_cursor: int | None = None
    persisted_ids = [row.id for row in rows if row.id is not None]
    if persisted_ids:
        oldest_id = min(persisted_ids)
        if await _has_older_messages(db, chat_list_id, oldest_id):
            next_cursor = oldest_id

    return ConversationPageResponse(
        messages=[ConversationResponse.model_validate(m) for m in messages],
        next_cursor_id=next_cursor,
    )


async def get_conversation_list_for_user(chat_list_id: int, user_id: int, db: AsyncSession) -> ConversationList:
    result = await db.execute(
        select(ConversationList).where(
            ConversationList.id == chat_list_id,
            ConversationList.user_id == user_id,
            ConversationList.is_active == True,  # noqa: E712
        )
    )
    conversation_list = result.scalars().first()
    if not conversation_list:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation_list
