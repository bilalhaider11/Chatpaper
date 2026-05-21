from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from models.conversation import ConversationList, Conversation
from schema.conversation import ConversationListBase


def create_conversation_list(current_user, db: Session):
    db_data = ConversationList(
        user_id=current_user.id,
        conversation_title="start chat",
        is_active=True,
    )
    db.add(db_data)
    db.commit()
    db.refresh(db_data)
    return db_data


def update_conversation_title(title: ConversationListBase, conversation_id: int, session: Session):
    if not title or not title.conversation_title:
        raise HTTPException(status_code=400, detail="No title to update")

    statement = (
        update(ConversationList)
        .where(ConversationList.id == conversation_id)
        .values(conversation_title=title.conversation_title)
    )

    session.execute(statement)
    session.commit()

    return {"Title": "Updated Successfully"}


def add_conversation(data, chat_id, db):
    if not chat_id:
        raise HTTPException(status_code=400, detail="Chat does not exist")

    statement = Conversation(
        chat_id=chat_id,
        user_type=data.user_type,
        statement=data.statement,
    )

    db.add(statement)
    db.commit()
    db.refresh(statement)

    return statement


def get_conversations(chat_list_id, db):
    if not chat_list_id:
        raise HTTPException(status_code=400, detail="Chat does not exist")

    conversations = (
        db.query(Conversation)
        .order_by(Conversation.created_at.asc())
        .where(Conversation.chat_id == chat_list_id)
        .all()
    )
    return conversations
