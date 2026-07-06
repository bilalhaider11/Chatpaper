from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.config import settings
from core.auth import get_current_user
from core.dependencies import get_db
from core.limiter import limiter
from core.llm import get_chat_llm
from models.auth import UserRole
from models.conversation import Conversation, ConversationList
from schema.chat import AskRequest, AskResponse
from services import rag as rag_service
from services.credits import deduct_credits

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/{conversation_id}/ask", response_model=AskResponse)
@limiter.limit("20/minute")
async def ask(
    request: Request,
    conversation_id: int,
    body: AskRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        get_chat_llm(temperature=0.2)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="LLM dependencies not installed")

    stmt = select(ConversationList).where(
        ConversationList.id == conversation_id,
        ConversationList.is_active == True,  # noqa: E712
    )
    if current_user.role != UserRole.admin:
        stmt = stmt.where(ConversationList.user_id == current_user.id)
    result = await db.execute(stmt)
    convo = result.scalars().first()
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await deduct_credits(current_user.id, settings.CREDIT_COST_CHAT, db)

    answer, citations = await rag_service.run_rag(
        question=body.question,
        convo=convo,
        db=db,
        top_k=body.top_k,
        use_summary_routing=body.use_summary_routing,
        use_bm25=body.use_bm25,
        use_propositions=body.use_propositions,
    )

    db.add(Conversation(chat_id=conversation_id, user_type="user", statement=body.question))
    db.add(Conversation(chat_id=conversation_id, user_type="assistant", statement=answer))
    await db.commit()

    return AskResponse(answer=answer, citations=citations, conversation_id=conversation_id)
