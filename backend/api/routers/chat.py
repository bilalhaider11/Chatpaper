from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.config import settings
from core.dependencies import get_db
from models.auth import UserRole
from models.conversation import Conversation, ConversationList
from schema.chat import AskRequest, AskResponse, Citation
from services.retrieval import RetrievedContext, retrieve

try:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None  # type: ignore[assignment,misc]
    AIMessage = None  # type: ignore[assignment,misc]
    HumanMessage = None  # type: ignore[assignment,misc]
    SystemMessage = None  # type: ignore[assignment,misc]

router = APIRouter(prefix="/chat", tags=["chat"])


def _context_block(ctx: RetrievedContext, index: int) -> str:
    pages = f"pages {ctx.page_start}–{ctx.page_end}" if ctx.page_start else "page unknown"
    return f"[{index}] {ctx.filename} ({pages})\n{ctx.content}"


def _system_prompt(contexts: list[RetrievedContext]) -> str:
    if not contexts:
        return (
            "You are a research assistant. "
            "No relevant document context was found for this query."
        )
    context_text = "\n\n---\n\n".join(_context_block(c, i + 1) for i, c in enumerate(contexts))
    return (
        "You are a research assistant. Answer using ONLY the document context below. "
        "Cite sources with [N] notation matching the context numbers. "
        "If the answer is not in the context, say so — do not fabricate.\n\n"
        f"Document context:\n\n{context_text}"
    )


@router.post("/{conversation_id}/ask", response_model=AskResponse)
async def ask(
    conversation_id: int,
    body: AskRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if ChatOpenAI is None:
        raise HTTPException(status_code=503, detail="LLM dependencies not installed")

    q = db.query(ConversationList).filter(ConversationList.id == conversation_id)
    if current_user.role != UserRole.admin:
        q = q.filter(ConversationList.user_id == current_user.id)
    convo = q.first()
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # use the conversation owner's id so retrieval hits the right user's vectors
    contexts = retrieve(
        query=body.question,
        user_id=convo.user_id,
        db=db,
        file_ids=body.file_ids,
        top_k=body.top_k,
        use_summary_routing=body.use_summary_routing,
        use_bm25=body.use_bm25,
        use_propositions=body.use_propositions,
    )

    # last 6 turns for multi-turn context (fetched in reverse, then flipped)
    history = (
        db.query(Conversation)
        .filter(Conversation.chat_id == conversation_id)
        .order_by(Conversation.created_at.desc())
        .limit(6)
        .all()
    )
    history.reverse()

    messages = [SystemMessage(content=_system_prompt(contexts))]
    for turn in history:
        if turn.user_type == "user":
            messages.append(HumanMessage(content=turn.statement))
        else:
            messages.append(AIMessage(content=turn.statement))
    messages.append(HumanMessage(content=body.question))

    llm = ChatOpenAI(
        model=settings.openai_chat_model,
        temperature=0.2,
        api_key=settings.openai_api_key,
    )
    answer: str = llm.invoke(messages).content

    db.add(Conversation(chat_id=conversation_id, user_type="user", statement=body.question))
    db.add(Conversation(chat_id=conversation_id, user_type="assistant", statement=answer))
    db.commit()

    citations = [
        Citation(
            file_id=c.file_id,
            filename=c.filename,
            page_start=c.page_start,
            page_end=c.page_end,
            content_preview=c.content[:300],
        )
        for c in contexts
    ]

    return AskResponse(answer=answer, citations=citations, conversation_id=conversation_id)
