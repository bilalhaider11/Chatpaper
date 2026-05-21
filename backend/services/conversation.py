from fastapi import HTTPException
from jose import JWTError, jwt
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from core.config import settings
from models.conversation import Conversation, ConversationList
from services import auth

def create_conversation_list( current_user, db:Session):
    
    db_data = ConversationList(
        user_id = current_user.id,
        conversation_title="start chat",
        is_active=True
        
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


def get_conversations(chat_list_id, db):
    
    if not chat_list_id:
        raise HTTPException(status_code=400,detail="Chat does not exist")
    
    conversations = db.query(Conversation).order_by(Conversation.created_at.asc()).where(Conversation.chat_id == chat_list_id).all()
    return conversations

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