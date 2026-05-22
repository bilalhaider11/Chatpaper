import asyncio
import json
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.config import settings
from core.dependencies import get_db
from models.conversation import ConversationList
from schema.conversation import (
    ChatWsSendPayload,
    ConversationListResponse,
    ConversationResponse,
)
from core.websocket import manager
from core.dependencies import get_db
from models.auth import User, UserRole
from models.conversation import ConversationList
from schema.conversation import ConversationListBase, ConversationListResponse, ConversationResponse
from services import conversation as conversation_service
from services.messaging import (
    USER_TYPE_SYSTEM,
    publish_chat_message,
)
router = APIRouter(prefix="/conversation", tags=["conversation"])


async def _stream_system_message(chat_list_id: int, statement: str, temp_id: str, user_type:str) -> None:
    chunk_size = settings.chat_stream_chunk_size
    for index in range(0, len(statement), chunk_size):
        chunk = statement[index : index + chunk_size]
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


def _get_owned_convo(db: Session, convo_id: int, user: User) -> ConversationList:
    convo = db.query(ConversationList).filter(ConversationList.id == convo_id).first()
    if convo is None or (user.role != UserRole.admin and convo.user_id != user.id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo


@router.post("/inconversationlist", response_model=ConversationListResponse)
async def conversation_list(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return conversation_service.create_conversation_list(current_user, db)


@router.patch("/conversation-title/{conversation_id}")
async def update_conversation_title(
    conversation_id: int,
    title: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_convo(db, conversation_id, current_user)
    return conversation_service.update_conversation_title(title, conversation_id, db)


@router.get("/get_conversation_list", response_model=list[ConversationListResponse])
async def get_conversation_list(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(ConversationList).where(ConversationList.is_active == True)
    if current_user.role != UserRole.admin:
        q = q.where(ConversationList.user_id == current_user.id)
    return q.all()


@router.post("/conversation/{chat_id}", response_model=ConversationResponse)
async def conversation(
    chat_id: int,
    data: ConversationResponse,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_convo(db, chat_id, current_user)
    return conversation_service.add_conversation(data, chat_id, db)


@router.get("/get-conversation/{chat_list_id}", response_model=list[ConversationResponse])
async def get_conversation(
    chat_list_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_convo(db, chat_list_id, current_user)
    return conversation_service.get_conversations(chat_list_id, db)


@router.delete("/delete_list/{list_id}")
async def delete_conversation_list(
    list_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return conversation_service.delete_conversation_list(list_id, db)


@router.websocket("/ws/{chat_list_id}")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    chat_list_id: int,
    token: str | None = None,
):
    if not token:
        await websocket.close(code=4401)
        return

    db = next(get_db())
    try:
        current_user = get_current_user(token,db)
        
        #current_user = conversation_service.get_user_from_token(token, db)
        conversation_service.get_conversation_list_for_user(
            chat_list_id, current_user.id, db
        )
    except HTTPException:
        await websocket.close(code=4401)
        return
    finally:
        db.close()
# db connection closes and next work to websockets
    await manager.connect(websocket, chat_list_id)
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
                data.user_type,
                data.statement,
            )
    except WebSocketDisconnect:
        manager.disconnect(websocket, chat_list_id)
#why in stream_system_message we have loop and checking with chunk for user-type system, and why chunk and for what it is used, btw its value is 12?