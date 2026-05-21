from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from models.auth import User
from models.conversation import Conversation, ConversationList
from schema.conversation import ConversationListBase, ConversationResponse


def create_conversation_list(current_user: User, db: Session) -> ConversationList:
    db_data = ConversationList(
        user_id=current_user.id,
        conversation_title="start chat",
        is_active=True,
    )
    db.add(db_data)
    db.commit()
    db.refresh(db_data)
    return db_data


def update_conversation_title(
    title: ConversationListBase, conversation_id: int, session: Session
) -> dict:
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


def add_conversation(data: ConversationResponse, chat_id: int, db: Session) -> Conversation:
    if not chat_id:
        raise HTTPException(status_code=400, detail="Chat does not exist")

    row = Conversation(
        chat_id=chat_id,
        user_type=data.user_type,
        statement=data.statement,
    )

    db.add(row)
    db.commit()
    db.refresh(row)

    return row


def get_conversations(chat_list_id: int, db: Session) -> list[Conversation]:
    if not chat_list_id:
        raise HTTPException(status_code=400, detail="Chat does not exist")

    return (
        db.query(Conversation)
        .order_by(Conversation.created_at.asc())
        .where(Conversation.chat_id == chat_list_id)
        .all()
    )
