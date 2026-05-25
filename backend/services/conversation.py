from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from models.conversation import Conversation, ConversationList
from models.file_model import FileRecord
from schema.conversation import ConversationCreateRequest, ConversationListBase
from services.chat_cache import get_active_streams, get_pending_messages


def create_conversation_list(current_user, body: ConversationCreateRequest, db: Session) -> ConversationList:
    db_data = ConversationList(
        user_id=current_user.id,
        conversation_title=body.conversation_title,
        conversation_type=body.conversation_type,
        is_active=True,
    )
    db.add(db_data)
    db.commit()
    db.refresh(db_data)
    return db_data


def delete_conversation(convo_id: int, db: Session) -> dict:
    convo = db.query(ConversationList).filter(ConversationList.id == convo_id).first()
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if convo.conversation_type == "per_file" and convo.file_id is not None:
        file_record = db.query(FileRecord).filter(FileRecord.id == convo.file_id).first()
        if file_record is not None:
            file_record.is_active = False

    convo.is_active = False
    db.commit()
    return {"message": "Conversation deleted successfully"}


def update_conversation_title(title: ConversationListBase, conversation_id: int, session: Session) -> dict:
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


async def get_conversations(chat_list_id, db):
    if not chat_list_id:
        raise HTTPException(status_code=400, detail="Chat does not exist")

    conversations = (
        db.query(Conversation)
        .order_by(Conversation.created_at.asc())
        .where(Conversation.chat_id == chat_list_id)
        .limit(25)
    )

    pending = await get_pending_messages(chat_list_id)
    streams = await get_active_streams(chat_list_id)

    merged: list = list(conversations)
    for msg in pending:
        merged.append(
            Conversation(
                id=None,
                chat_id=msg.chat_id,
                user_type=msg.user_type,
                statement=msg.statement,
            )
        )
    for stream in streams:
        merged.append(
            Conversation(
                id=None,
                chat_id=chat_list_id,
                user_type=stream["user_type"],
                statement=stream["statement"],
            )
        )
    return merged


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
