import asyncio
import contextlib
import json
import logging
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user
from core.config import settings
from core.database import AsyncSessionLocal
from core.dependencies import get_db
from core.websocket import manager
from models.auth import User, UserRole
from models.conversation import ConversationList
from schema.conversation import (
    ChatWsSendPayload,
    ConversationCreateRequest,
    ConversationListResponse,
    ConversationResponse,
)
from services import conversation as conversation_service
from services.chat_cache import append_stream_chunk, clear_stream
from services.messaging import (
    USER_TYPE_SYSTEM,
    publish_chat_message,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversation", tags=["conversation"])


async def _stream_system_message(chat_list_id: int, statement: str, temp_id: str, user_type: str) -> None:
    chunk_size = settings.chat_stream_chunk_size
    for index in range(0, len(statement), chunk_size):
        chunk = statement[index : index + chunk_size]
        await append_stream_chunk(chat_list_id, temp_id, chunk)
        await manager.broadcast(
            chat_list_id,
            {
                "type": "chunk",
                "temp_id": temp_id,
                "user_type": user_type,
                "chunk": chunk,
                "chat_id": chat_list_id,
            },
        )
        await asyncio.sleep(0.03)

    await clear_stream(chat_list_id, temp_id)


async def _handle_outgoing_message(chat_list_id: int, user_type: str, statement: str) -> str:
    temp_id = str(uuid4())
    statement = statement.strip()
    if not statement:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    if user_type == USER_TYPE_SYSTEM:
        await _stream_system_message(chat_list_id, statement, temp_id, user_type)

    await manager.broadcast(
        chat_list_id,
        {
            "type": "message",
            "temp_id": temp_id,
            "user_type": user_type,
            "statement": statement,
            "chat_id": chat_list_id,
        },
    )

    await publish_chat_message(
        chat_id=chat_list_id,
        user_type=user_type,
        statement=statement,
        temp_id=temp_id,
    )
    return temp_id


async def _get_owned_convo(db: AsyncSession, convo_id: int, user: User) -> ConversationList:
    result = await db.execute(
        select(ConversationList).where(
            ConversationList.id == convo_id,
            ConversationList.is_active == True,  # noqa: E712
        )
    )
    convo = result.scalars().first()
    if convo is None or (user.role != UserRole.admin and convo.user_id != user.id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo


@router.post("/inconversationlist", response_model=ConversationListResponse)
async def conversation_list(
    body: ConversationCreateRequest | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body is None:
        body = ConversationCreateRequest()
    return await conversation_service.create_conversation_list(current_user, body, db)


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_convo(db, conversation_id, current_user)
    return await conversation_service.delete_conversation(conversation_id, db)


@router.patch("/conversation-title/{conversation_id}")
async def update_conversation_title(
    conversation_id: int,
    title: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_convo(db, conversation_id, current_user)
    return await conversation_service.update_conversation_title(title, conversation_id, db)


@router.get(
    "/get_conversation_list",
    response_model=list[ConversationListResponse],
)
async def get_conversation_list(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ConversationList)
        .where(
            ConversationList.is_active == True,  # noqa: E712
            ConversationList.user_id == current_user.id,
        )
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.get("/get-conversation/{chat_list_id}", response_model=list[ConversationResponse])
async def get_conversation(
    chat_list_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_convo(db, chat_list_id, current_user)
    return await conversation_service.get_conversations(chat_list_id, db, limit=limit, offset=offset)


@router.delete("/delete_list/{list_id}")
async def delete_conversation_list(
    list_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_convo(db, list_id, current_user)
    return await conversation_service.delete_conversation_list(list_id, db)


async def _redis_listener(channel: str, websocket: WebSocket) -> None:
    """Subscribe to a Redis pub/sub channel and forward messages to the WebSocket.

    Retries on Redis errors so a transient Redis disconnect doesn't silently
    kill the WebSocket. Exits permanently when the WebSocket closes or the
    task is cancelled.
    """
    from core.redis_client import get_redis
    while True:
        redis = get_redis()
        if redis is None:
            return  # no Redis; broadcast uses local fallback path
        pubsub = redis.pubsub()
        try:
            await pubsub.subscribe(channel)
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        await websocket.send_text(message["data"])
                    except Exception:
                        return  # WebSocket closed
        except asyncio.CancelledError:
            return
        except Exception:
            logger.warning("Redis pub/sub error on %s, retrying in 1s", channel)
            await asyncio.sleep(1)
        finally:
            with contextlib.suppress(Exception):
                await pubsub.aclose()


@router.websocket("/ws/{chat_list_id}")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    chat_list_id: int,
    token: str | None = None,
):
    if not token:
        await websocket.close(code=4401)
        return

    async with AsyncSessionLocal() as db:
        try:
            current_user = await get_current_user(token, db)
            await conversation_service.get_conversation_list_for_user(
                chat_list_id, current_user.id, db
            )
        except HTTPException:
            await websocket.close(code=4401)
            return

    await manager.connect(websocket, chat_list_id)
    listener_task = asyncio.create_task(
        _redis_listener(manager.room_channel(chat_list_id), websocket)
    )
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
                data = ChatWsSendPayload(**payload)
            except Exception:
                await websocket.send_text(
                    json.dumps({"type": "error", "detail": "Invalid message payload"})
                )
                continue

            if data.action != "send":
                continue

            await _handle_outgoing_message(
                chat_list_id,
                "user",
                data.statement,
            )
    except WebSocketDisconnect:
        listener_task.cancel()
        manager.disconnect(websocket, chat_list_id)
    except Exception:
        listener_task.cancel()
        manager.disconnect(websocket, chat_list_id)
        raise
