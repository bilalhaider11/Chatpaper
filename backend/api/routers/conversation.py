from pathlib import Path
from uuid import uuid4
import shutil

from fastapi import Body,APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from core.dependencies import get_db
from models.conversation import Conversation,ConversationList
from schema.conversation import ConversationListResponse, ConversationResponse, ConversationListBase
from core.auth import get_current_user
from services import conversation as conversation_service
router = APIRouter(prefix="/conversation", tags=["conversation"])

    
@router.post("/inconversationlist", response_model=ConversationListResponse)
async def conversation_list(
    
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return conversation_service.create_conversation_list(current_user,db)
    
    

@router.patch("/conversation-title/{conversation_id}")
async def update_conversation_title(
    conversation_id: int,
    title: str = Body(..., embed=True),
    current_user=Depends(get_current_user),
    db: Session=Depends(get_db)   
):
    return conversation_service.update_conversation_title(title ,conversation_id, db)

@router.get("/get_conversation_list",response_model=list[ConversationListResponse])
async def get_conersation_list(
    current_user=Depends(get_current_user),
    db: Session=Depends(get_db)):
 
    
    return db.query(ConversationList).where(ConversationList.user_id == current_user.id , ConversationList.is_active == True).all()
    

@router.post("/conversation/{chat_id}",response_model=ConversationResponse)
async def conversation(
    chat_id:int,
    data: ConversationResponse,
    current_user=Depends(get_current_user),
    db: Session=Depends(get_db)
):
    
    return conversation_service.add_conversation(data, chat_id, db)


@router.get("/get-conversation/{chat_list_id}",response_model=list[ConversationResponse])
async def get_conversation(
    chat_list_id:int,
    current_user=Depends(get_current_user),
    db: Session=Depends(get_db)
):
    return conversation_service.get_conversations(chat_list_id, db)
    

@router.delete("/delete_list/{list_id}")
async def delete_conversation_list(
    list_id:int,
    current_user=Depends(get_current_user),
    db:Session=Depends(get_db)
):
    return conversation_service.delete_conversation_list(list_id, db)