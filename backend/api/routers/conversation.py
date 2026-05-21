from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.dependencies import get_db
from models.auth import UserRole
from models.conversation import Conversation, ConversationList
from schema.conversation import ConversationListResponse, ConversationResponse, ConversationListBase
from core.auth import get_current_user
from services import conversation as conversation_service

router = APIRouter(prefix="/conversation", tags=["conversation"])


@router.post("/inconversationlist", response_model=ConversationListResponse)
async def conversation_list(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return conversation_service.create_conversation_list(current_user, db)


@router.patch("/conversation-title/{conversation_id}")
async def update_conversation_title(
    conversation_id: int,
    title: ConversationListBase,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    convo = db.query(ConversationList).filter(ConversationList.id == conversation_id).first()
    if convo is None or (
        current_user.role != UserRole.admin and convo.user_id != current_user.id
    ):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation_service.update_conversation_title(title, conversation_id, db)


@router.get("/get_conversation_list", response_model=list[ConversationListResponse])
async def get_conversation_list(
    current_user=Depends(get_current_user),
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
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    convo_list = db.query(ConversationList).filter(ConversationList.id == chat_id).first()
    if convo_list is None or (
        current_user.role != UserRole.admin and convo_list.user_id != current_user.id
    ):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation_service.add_conversation(data, chat_id, db)


@router.get("/get-conversation/{chat_list_id}", response_model=list[ConversationResponse])
async def get_conversation(
    chat_list_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    convo_list = db.query(ConversationList).filter(ConversationList.id == chat_list_id).first()
    if convo_list is None or (
        current_user.role != UserRole.admin and convo_list.user_id != current_user.id
    ):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation_service.get_conversations(chat_list_id, db)
