from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.dependencies import get_db
from models.auth import User, UserRole
from models.conversation import ConversationList
from schema.conversation import ConversationListBase, ConversationListResponse, ConversationResponse
from services import conversation as conversation_service

router = APIRouter(prefix="/conversation", tags=["conversation"])


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
    title: ConversationListBase,
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
