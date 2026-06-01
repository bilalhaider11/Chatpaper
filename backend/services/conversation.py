from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.conversation import Conversation, ConversationList
from models.file_model import FileRecord
from schema.conversation import ConversationCreateRequest
from services.chat_cache import get_active_streams, get_pending_messages


async def create_conversation_list(current_user, body: ConversationCreateRequest, db: AsyncSession) -> ConversationList:
    db_data = ConversationList(
        user_id=current_user.id,
        conversation_title=body.conversation_title,
        conversation_type=body.conversation_type,
        is_active=True,
    )
    db.add(db_data)
    await db.commit()
    await db.refresh(db_data)
    return db_data


async def delete_conversation(convo_id: int, db: AsyncSession) -> dict:
    result = await db.execute(select(ConversationList).where(ConversationList.id == convo_id))
    convo = result.scalars().first()
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if convo.conversation_type == "per_file" and convo.file_id is not None:
        fr = await db.execute(select(FileRecord).where(FileRecord.id == convo.file_id))
        file_record = fr.scalars().first()
        if file_record is not None:
            file_record.is_active = False

    convo.is_active = False
    await db.commit()
    return {"message": "Conversation deleted successfully"}


async def update_conversation_title(title: str, conversation_id: int, session: AsyncSession) -> dict:
    if not title or not title.strip():
        raise HTTPException(status_code=400, detail="No title to update")

    stmt = (
        update(ConversationList)
        .where(ConversationList.id == conversation_id)
        .values(conversation_title=title)
    )
    await session.execute(stmt)
    await session.commit()
    return {"Title": "Updated Successfully"}


async def delete_conversation_list(list_id: int, db: AsyncSession) -> dict:
    result = await db.execute(select(ConversationList).where(ConversationList.id == list_id))
    convo = result.scalars().first()
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if convo.conversation_type == "per_file" and convo.file_id is not None:
        fr = await db.execute(select(FileRecord).where(FileRecord.id == convo.file_id))
        file_record = fr.scalars().first()
        if file_record is not None:
            file_record.is_active = False

    convo.is_active = False
    await db.commit()
    return {"message": "Conversation list deleted successfully"}


async def get_conversations(chat_list_id, db: AsyncSession, limit: int = 50, offset: int = 0):
    if not chat_list_id:
        raise HTTPException(status_code=400, detail="Chat does not exist")

    result = await db.execute(
        select(Conversation)
        .where(Conversation.chat_id == chat_list_id)
        .order_by(Conversation.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    conversations = list(result.scalars().all())

    pending = await get_pending_messages(chat_list_id)
    streams = await get_active_streams(chat_list_id)

    merged: list = conversations
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


async def get_conversation_list_for_user(chat_list_id: int, user_id: int, db: AsyncSession) -> ConversationList:
    result = await db.execute(
        select(ConversationList).where(
            ConversationList.id == chat_list_id,
            ConversationList.user_id == user_id,
            ConversationList.is_active == True,  # noqa: E712
        )
    )
    conversation_list = result.scalars().first()
    if not conversation_list:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation_list
