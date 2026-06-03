import json
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from models.conversation import Conversation, ConversationList
from models.file_model import FileRecord
from core.config import settings
from core.redis_client import get_redis
from services.chat_cache import get_active_streams, get_pending_messages


def _get_owned_file_for_user(db: Session, file_id: int, user_id: int) -> FileRecord:
    record = (
        db.query(FileRecord)
        .filter(
            FileRecord.id == file_id,
            FileRecord.user_id == user_id,
            FileRecord.is_active == True,
        )
        .first()
    )
    if record is None:
        raise HTTPException(
            status_code=400,
            detail="A valid uploaded file is required to start a conversation.",
        )
    return record


def create_conversation_list(current_user, db: Session, file_id: int):
    file_record = _get_owned_file_for_user(db, file_id, current_user.id)

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
    db.commit()
    db.refresh(db_data)
    
    return db_data

def update_conversation_title(title ,conversation_id, session):
    
    if not title:
        raise HTTPException(status_code=400, datail="No title to update")
    
    statement = (
        update(ConversationList)
        .where(ConversationList.id == conversation_id)
        .values(conversation_title=title)
    )
    
    session.execute(statement)
    session.commit()
    
    return {"Title": "Updated Successfully"}


def add_conversation(data, chat_id, db):
    
    if not chat_id:
        raise HTTPException(status_code=400,detail="Chat does not exist")
    
    statement = Conversation(
        chat_id=chat_id,
        user_type=data.user_type,
        statement=data.statement
        
    )
    
    db.add(statement)
    db.commit()
    db.refresh(statement)
    
    return statement


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


def _has_older_messages(db: Session, chat_list_id: int, oldest_id: int) -> bool:
    return (
        db.query(Conversation.id)
        .filter(
            Conversation.chat_id == chat_list_id,
            Conversation.id < oldest_id,
        )
        .first()
        is not None
    )


def _next_cursor_for_oldest(db: Session, chat_list_id: int, messages: list[dict]) -> int | None:
    ids = [m["id"] for m in messages if m.get("id") is not None]
    if not ids:
        return None
    oldest_id = min(ids)
    return oldest_id if _has_older_messages(db, chat_list_id, oldest_id) else None


async def _sync_newer_messages_into_cache(
    redis_client,
    chat_list_id: int,
    db: Session,
    cached_rows: list[dict],
) -> list[dict]:
    cached_ids = [row["id"] for row in cached_rows if row.get("id") is not None]
    if not cached_ids:
        return cached_rows

    max_id = max(cached_ids)
    newer = (
        db.query(Conversation)
        .filter(
            Conversation.chat_id == chat_list_id,
            Conversation.id > max_id,
        )
        .order_by(Conversation.created_at.asc(), Conversation.id.asc())
        .all()
    )
    if not newer:
        return cached_rows

    merged = _merge_messages_asc(
        [_cache_row_to_message(row) for row in cached_rows],
        [_conversation_row_to_message(row) for row in newer],
    )
    merged_rows = [_message_to_cache_row(msg) for msg in merged]
    await _save_cached_history_rows(redis_client, chat_list_id, merged_rows)
    return merged_rows


async def get_conversations(chat_list_id: int, db: Session, limit: int = 25, cursor_id: int | None = None):
    
    if not chat_list_id:
        raise HTTPException(status_code=400, detail="Chat does not exist")
    if limit <= 0 or limit > 100:
        raise HTTPException(status_code=400, detail="Invalid limit")

    redis_client = get_redis()

    # Load DB page in *chronological* (asc) order for the UI.
    db_messages: list[dict] = []
    next_cursor_id: int | None = None

    if cursor_id is None and redis_client is not None:
        cached_rows = await _load_cached_history_rows(redis_client, chat_list_id)
        if cached_rows:
            cached_rows = await _sync_newer_messages_into_cache(
                redis_client, chat_list_id, db, cached_rows
            )
            db_messages = [_cache_row_to_message(row) for row in cached_rows]
            next_cursor_id = _next_cursor_for_oldest(db, chat_list_id, db_messages)

    if cursor_id is not None or not db_messages:
        query = db.query(Conversation).where(Conversation.chat_id == chat_list_id)
        if cursor_id is not None:
            query = query.where(Conversation.id < cursor_id)

        rows_desc = (
            query.order_by(Conversation.created_at.desc(), Conversation.id.desc())
            .limit(limit)
            .all()
        )
        if len(rows_desc) == limit and rows_desc:
            next_cursor_id = rows_desc[-1].id

        rows_asc = list(reversed(rows_desc))
        page_messages = [_conversation_row_to_message(row) for row in rows_asc]

        if cursor_id is None:
            db_messages = page_messages
            if redis_client is not None:
                await _save_cached_history_rows(
                    redis_client,
                    chat_list_id,
                    [_message_to_cache_row(msg) for msg in db_messages],
                )
        else:
            db_messages = page_messages
            if redis_client is not None:
                cached_rows = await _load_cached_history_rows(redis_client, chat_list_id)
                if cached_rows:
                    cached_messages = [_cache_row_to_message(row) for row in cached_rows]
                else:
                    cached_messages = []
                merged = _merge_messages_asc(cached_messages, page_messages)
                await _save_cached_history_rows(
                    redis_client,
                    chat_list_id,
                    [_message_to_cache_row(msg) for msg in merged],
                )

            
    pending = await get_pending_messages(chat_list_id)
    streams = await get_active_streams(chat_list_id)

    merged_by_temp: dict[str, dict] = {}
    merged_without_temp: list[dict] = []

    def _temp_key(m: dict) -> str | None:
        temp_id = m.get("temp_id")
        return temp_id if temp_id else None

    for msg in pending:
        created_at = (
            datetime.fromisoformat(msg.enqueued_at) if msg.enqueued_at else None
        )  # enqueued_at is the best proxy for display ordering
        m = {
            "id": None,
            "chat_id": msg.chat_id,
            "temp_id": msg.temp_id,
            "created_at": created_at,
            "user_type": msg.user_type,
            "statement": msg.statement,
            "streaming": False,
        }
        key = _temp_key(m)
        if key:
            merged_by_temp[key] = m
        else:
            merged_without_temp.append(m)

    for stream in streams:
        created_at_raw = stream.get("created_at")
        created_at = (
            datetime.fromisoformat(created_at_raw) if created_at_raw else None
        )
        m = {
            "id": None,
            "chat_id": chat_list_id,
            "temp_id": stream["temp_id"],
            "created_at": created_at,
            "user_type": stream["user_type"],
            "statement": stream["statement"],
            "streaming": True,
        }
        # If a temp_id exists already (pending), prefer the active stream representation.
        key = _temp_key(m)
        if key:
            merged_by_temp[key] = m
        else:
            merged_without_temp.append(m)

    merged: list[dict] = []
    merged.extend(db_messages)
    merged.extend(list(merged_by_temp.values()))
    merged.extend(merged_without_temp)

    merged.sort(key=_message_sort_ts)

    return {"messages": merged, "next_cursor_id": next_cursor_id}

def delete_conversation_list(id, db):
    
    statement = (
        update(ConversationList)
        .where(ConversationList.id == id)
        .values(is_active=False)
    )
    
    db.execute(statement)
    db.commit()
    
    return {"Title": "deleted Successfully"}

def get_conversation_list_for_user(chat_list_id: int, user_id: int, db: Session) -> ConversationList:
    conversation_list = (
        db.query(ConversationList)
        .filter(
            ConversationList.id == chat_list_id,
            ConversationList.user_id == user_id,
            ConversationList.is_active == True,
        )
        .first()
    )
    if not conversation_list:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation_list