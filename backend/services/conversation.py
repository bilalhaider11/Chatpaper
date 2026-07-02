from fastapi import HTTPException
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_
from sqlalchemy.orm import aliased
from models.conversation import (
    Conversation,
    ConversationList,
    CombinedSharedConversationImport,
)
from models.file_model import FileRecord
from schema.conversation import ConversationCreateRequest, PaginatedConversationResponse
from services.chat_cache import (
    get_active_streams,
    get_cached_conversation_messages,
    get_pending_messages,
    set_cached_conversation_messages,
)
from core.config import settings


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


async def update_conversation_title(title: str, conversation_id: int, user_id: int, session: AsyncSession) -> dict:
    if not title or not title.strip():
        raise HTTPException(status_code=400, detail="No title to update")

    stmt = (
        update(ConversationList)
        .where(ConversationList.id == conversation_id, ConversationList.user_id == user_id)
        .values(conversation_title=title)
    )
    await session.execute(stmt)
    await session.commit()
    return {"Title": "Updated Successfully"}

async def mark_chat_shared(conversation_list_id: int, user, db: AsyncSession) -> dict:
    result = await db.execute(
        select(ConversationList).where(ConversationList.id == conversation_list_id)
    )
    conversation = result.scalars().first()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation.conversation_type == "shared global" or conversation.conversation_type == "shared per_file":
        raise HTTPException(status_code=403, detail="Cannot share imported conversation")
    
    message_count = await db.scalar(
        select(func.count(Conversation.id)).where(Conversation.chat_id == conversation_list_id)
    )
    
    combined_shared_conversation = CombinedSharedConversationImport(
        limit=message_count or 0,
        shared_user_id=user.id,
        shared_chat_id=conversation_list_id
    )
    db.add(combined_shared_conversation)
    await db.commit()
    await db.refresh(combined_shared_conversation)

    share_url = f"{settings.frontend_url}/conversation/share/{combined_shared_conversation.id}"
    return {"share_url": share_url, "shared_id": combined_shared_conversation.id}


async def get_merged_messages(
    chat_list_id: int,
    db: AsyncSession,
) -> list[Conversation]:

    result = await db.execute(
        select(
            ConversationList,
            CombinedSharedConversationImport,
        )
        .outerjoin(
            CombinedSharedConversationImport,
            CombinedSharedConversationImport.id
            == ConversationList.shared_conversation_id,
        )
        .where(ConversationList.id == chat_list_id)
    )

    row = result.first()
    if row is None:
        return []

    _, shared_import = row

    chat_ids = [chat_list_id]
    if shared_import:
        chat_ids.append(shared_import.shared_chat_id)

    result = await db.execute(
        select(Conversation)
        .where(Conversation.chat_id.in_(chat_ids))
        .order_by(Conversation.created_at.asc())
    )

    conversations = result.scalars().all()

    if not shared_import:
        return list(conversations)

    shared_messages = []
    own_messages = []

    for conversation in conversations:
        if conversation.chat_id == shared_import.shared_chat_id:
            if len(shared_messages) < shared_import.limit:
                shared_messages.append(conversation)
        else:
            own_messages.append(conversation)

    merged = shared_messages + own_messages
    merged.sort(key=lambda c: c.created_at)

    return merged


async def get_chat_shared(shared_id: int, user, db: AsyncSession) -> dict:
    ImportedConversation = aliased(ConversationList)
    SourceConversation = aliased(ConversationList)

    result = await db.execute(
        select(
            CombinedSharedConversationImport,
            ImportedConversation,
            SourceConversation,
        )
        .outerjoin(
            ImportedConversation,
            and_(
                ImportedConversation.shared_conversation_id
                == CombinedSharedConversationImport.id,
                ImportedConversation.user_id == user.id,
                ImportedConversation.is_active == True,  # noqa: E712
            ),
        )
        .join(
            SourceConversation,
            SourceConversation.id
            == CombinedSharedConversationImport.shared_chat_id,
        )
        .where(
            CombinedSharedConversationImport.id == shared_id,
        )
    )

    row = result.first()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Shared conversation not found",
        )

    shared_record, imported_list, source_list = row

    if imported_list:
        return {
            "conversation_list": imported_list,
            "already_imported": True,
            "messages_imported": shared_record.limit,
        }

    if not source_list:
        raise HTTPException(
            status_code=404,
            detail="Original conversation no longer exists",
        )

    type_of_conv = (
        "shared global"
        if source_list.conversation_type == "global"
        else "shared per_file"
    )

    new_conversation_list = ConversationList(
        user_id=user.id,
        conversation_title=source_list.conversation_title,
        conversation_type=type_of_conv,
        is_active=True,
        file_id=source_list.file_id,
        shared_conversation_id=shared_id,
    )
    db.add(new_conversation_list)
    await db.commit()
    await db.refresh(new_conversation_list)

    return {
        "conversation_list": new_conversation_list,
        "already_imported": False,
        "messages_imported": shared_record.limit,
    }


def _conversation_to_cache_dict(conversation: Conversation) -> dict:
    return {
        "id": conversation.id,
        "chat_id": conversation.chat_id,
        "user_type": conversation.user_type,
        "statement": conversation.statement,
        "created_at":conversation.created_at,
    }


def _cache_dict_to_conversation(data: dict) -> Conversation:
    return Conversation(
        id=data.get("id"),
        chat_id=data.get("chat_id"),
        user_type=data["user_type"],
        statement=data["statement"],
        created_at=data["created_at"],
    )


async def _get_merged_messages_cached(chat_list_id: int, db: AsyncSession) -> list[Conversation]:
    cached = await get_cached_conversation_messages(chat_list_id)
    if cached is not None:
        return [_cache_dict_to_conversation(item) for item in cached]

    conversations = await get_merged_messages(chat_list_id, db)
    await set_cached_conversation_messages(
        chat_list_id,
        [_conversation_to_cache_dict(item) for item in conversations],
    )

    return conversations


async def get_conversations(
    chat_list_id: int,
    db: AsyncSession,
    limit: int | None = None,
    page: int = 0,
) -> PaginatedConversationResponse:
    if not chat_list_id:
        raise HTTPException(status_code=400, detail="Chat does not exist")

    page_size = limit or settings.chat_conversation_page_size
    if page < 0:
        raise HTTPException(status_code=400, detail="Page must be >= 0")

    all_conversations = await _get_merged_messages_cached(chat_list_id, db)
    total = len(all_conversations)

    end = total - page * page_size
    start = max(0, end - page_size)
    if end <= 0:
        page_messages: list[Conversation] = []
    else:
        page_messages = list(all_conversations[start:end])

    if page == 0:
        pending = await get_pending_messages(chat_list_id)
        streams = await get_active_streams(chat_list_id)
        for msg in pending:
            page_messages.append(
                Conversation(
                    id=None,
                    chat_id=msg.chat_id,
                    user_type=msg.user_type,
                    statement=msg.statement,
                    created_at=msg.created_at,
                )
            )
        for stream in streams:
            page_messages.append(
                Conversation(
                    id=None,
                    chat_id=chat_list_id,
                    user_type=stream["user_type"],
                    statement=stream["statement"],
                    created_at=stream["created_at"]
                )
            )

    return PaginatedConversationResponse(
        messages=page_messages,
        total=total,
        page=page,
        limit=page_size,
        has_more=start > 0,
    )


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
