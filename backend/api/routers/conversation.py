import asyncio
import contextlib
import json
import logging
from types import SimpleNamespace
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from services.messaging import handle_conversation_message
from core.auth import get_current_user
from core.database import AsyncSessionLocal
from core.dependencies import get_db
from core.llm import get_chat_llm
from core.websocket import manager
from models.auth import User, UserRole
from models.conversation import Conversation, ConversationList
from schema.conversation import (
    ChatWsSendPayload,
    ConversationCreateRequest,
    ConversationListResponse,
    ImportSharedConversationResponse,
    PaginatedConversationResponse,
    ShareConversationResponse,
)
from core.config import settings
from services import conversation as conversation_service
from services import rag as rag_service
from services.chat_cache import append_stream_chunk, clear_stream
from services.credits import deduct_credits,get_credits, mark_subcription_end

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversation", tags=["conversation"])


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

    result = await db.execute(
        select(ConversationList).where(
            ConversationList.conversation_type == body.conversation_type,
            ConversationList.user_id == current_user.id,
            ConversationList.is_active.is_(True),
        )
    )
    user_conversation = result.scalar_one_or_none()
    
    if user_conversation is not None:
        raise HTTPException(
            status_code=503,
            detail="Global conversation already exists"
        )
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
    return await conversation_service.update_conversation_title(title, conversation_id, current_user.id, db)


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


@router.get("/get-conversation/{chat_list_id}", response_model=PaginatedConversationResponse)
async def get_conversation(
    chat_list_id: int,
    limit: int = Query(10, ge=1, le=200),
    page: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_convo(db, chat_list_id, current_user)
    return await conversation_service.get_conversations(chat_list_id, db, limit=limit, page=page)

@router.post("/share/{conversation_list_id}", response_model=ShareConversationResponse)
async def share_conversation(
    conversation_list_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await conversation_service.mark_chat_shared(conversation_list_id, current_user, db)


@router.get("/shared/{shared_conversation_id}", response_model=ImportSharedConversationResponse)
async def get_shared_conversation(
    shared_conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await conversation_service.get_chat_shared(shared_conversation_id, current_user, db)

@router.delete("/delete_list/{list_id}")
async def delete_conversation_list(
    list_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_convo(db, list_id, current_user)
    return await conversation_service.delete_conversation(list_id, db)


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


async def _ws_ping_loop(websocket: WebSocket, interval: int = 25) -> None:
    """Send application-level pings so proxies don't kill idle connections during long LLM calls."""
    try:
        while True:
            await asyncio.sleep(interval)
            await websocket.send_text(json.dumps({"type": "ping"}))
    except (asyncio.CancelledError, Exception):
        pass


async def _handle_rag_stream(
    websocket: WebSocket,
    chat_list_id: int,
    convo: SimpleNamespace,
    question: str,
) -> None:
    """Run the full RAG pipeline for a user question and stream the AI response.

    Phases:
      1. Retrieve context + build messages (short DB session, released before LLM call)
      2. Stream LLM tokens — emit chunk events, accumulate in Redis stream cache
      3. On completion — clear cache, emit done, commit both rows atomically
    """
    try:
        llm = get_chat_llm(temperature=0.2)
    except RuntimeError:
        await websocket.send_text(json.dumps({"type": "error", "detail": "LLM unavailable"}))
        return
    
    await handle_conversation_message(
        chat_id=chat_list_id,
        user_type="user",
        statement=question,
    )

    # Phase 1: retrieve — use a short-lived session so the connection returns to pool during LLM call
    async with AsyncSessionLocal() as db:
        try:
            messages, contexts = await rag_service.prepare(question, convo, db)
        except Exception:
            logger.exception("RAG prepare failed for chat %s", chat_list_id)
            await websocket.send_text(json.dumps({"type": "error", "detail": "Failed to retrieve context"}))
            return

    # Phase 2: stream LLM tokens
    ai_temp_id = str(uuid4())
    full_answer = ""
    gen = llm.astream(messages)
    try:
        async for chunk in gen:
            token: str = chunk.content
            if not token:
                continue
            full_answer += token
            await append_stream_chunk(chat_list_id, ai_temp_id, token)
            await manager.broadcast(chat_list_id, {
                "type": "chunk",
                "temp_id": ai_temp_id,
                "user_type": "system",
                "chunk": token,
                "chat_id": chat_list_id,
            })
    except asyncio.CancelledError:
        await clear_stream(chat_list_id, ai_temp_id)
        raise
    except Exception:
        logger.exception("LLM stream failed for chat %s", chat_list_id)
        await clear_stream(chat_list_id, ai_temp_id)
        with contextlib.suppress(Exception):
            await websocket.send_text(json.dumps({"type": "error", "detail": "LLM stream failed"}))
        return
    finally:
        if hasattr(gen, "aclose"):
            await gen.aclose()

    await clear_stream(chat_list_id, ai_temp_id)

    if not full_answer.strip():
        with contextlib.suppress(Exception):
            await websocket.send_text(json.dumps({"type": "error", "detail": "Empty response from LLM"}))
        return

    citations = rag_service.extract_citations(full_answer, contexts)

    await manager.broadcast(chat_list_id, {
        "type": "done",
        "temp_id": ai_temp_id,
        "user_type": "system",
        "statement": full_answer,
        "citations": [c.model_dump() for c in citations],
        "chat_id": chat_list_id,
    })
    
    await handle_conversation_message(
        chat_id=chat_list_id,
        user_type="assistant",
        statement=full_answer,
    )


@router.websocket("/ws/{chat_list_id}")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    chat_list_id: int,
):
    await websocket.accept()

    # Auth handshake — client sends {"action": "auth", "token": "<jwt>"} as first frame
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        auth_payload = json.loads(raw)
        if auth_payload.get("action") != "auth" or not auth_payload.get("token"):
            await websocket.close(code=4401)
            return
        token: str = auth_payload["token"]
    except Exception:
        await websocket.close(code=4401)
        return

    # Validate token and ownership, snapshot convo fields before session closes
    async with AsyncSessionLocal() as db:
        try:
            current_user = await get_current_user(token, db)
            
            if  await get_credits(current_user.id, db) < settings.CREDIT_COST_CHAT:
                await mark_subcription_end(current_user.id,db)
                await websocket.send_text(
                    json.dumps({"type": "error", "detail": "Buy supscription to continue with the chats"})
                )
                
            _convo = await conversation_service.get_conversation_list_for_user(
                chat_list_id, current_user.id, db
            )
            convo = SimpleNamespace(
                id=_convo.id,
                conversation_type=_convo.conversation_type,
                file_id=_convo.file_id,
                user_id=_convo.user_id,
            )
        except HTTPException:
            await websocket.close(code=4401)
            return

    manager.register(websocket, chat_list_id)
    listener_task = asyncio.create_task(
        _redis_listener(manager.room_channel(chat_list_id), websocket)
    )
    ping_task = asyncio.create_task(_ws_ping_loop(websocket))

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

            question = data.statement.strip()
            if not question:
                continue

            async with AsyncSessionLocal() as credit_db:
                try:
                    await deduct_credits(convo.user_id, settings.CREDIT_COST_CHAT, credit_db)
                except HTTPException as exc:
                    await websocket.send_text(
                        json.dumps({"type": "error", "detail": exc.detail})
                    )
                    continue

            # Broadcast user's message to the room before streaming so other tabs see it immediately
            await manager.broadcast(chat_list_id, {
                "type": "message",
                "temp_id": str(uuid4()),
                "user_type": "user",
                "statement": question,
                "chat_id": chat_list_id,
            })

            await _handle_rag_stream(websocket, chat_list_id, convo, question)

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Unexpected error in WS handler for chat %s", chat_list_id)
    finally:
        listener_task.cancel()
        ping_task.cancel()
        manager.disconnect(websocket, chat_list_id)
