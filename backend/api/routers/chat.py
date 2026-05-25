import re

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
except ImportError:
    AIMessage = None  # type: ignore[assignment,misc]
    HumanMessage = None  # type: ignore[assignment,misc]
    SystemMessage = None  # type: ignore[assignment,misc]

from core.llm import get_chat_llm

router = APIRouter(prefix="/chat", tags=["chat"])

_CITATION_RE = re.compile(r"\[(\d+)\]")


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


def _truncate_history(history: list, max_chars: int) -> list:
    while history:
        total = sum(len(t.statement) for t in history)
        if total <= max_chars:
            break
        history = history[1:]
    return history


@router.post("/{conversation_id}/ask", response_model=AskResponse)
async def ask(
    conversation_id: int,
    body: AskRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        llm = get_chat_llm(temperature=0.2)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="LLM dependencies not installed")

    q = db.query(ConversationList).filter(ConversationList.id == conversation_id)
    if current_user.role != UserRole.admin:
        q = q.filter(ConversationList.user_id == current_user.id)
    convo = q.first()
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Fetch recent history FIRST so we can enrich the retrieval query with prior context.
    history = (
        db.query(Conversation)
        .filter(Conversation.chat_id == conversation_id)
        .order_by(Conversation.created_at.desc())
        .limit(settings.chat_history_turns)
        .all()
    )
    history.reverse()
    history = _truncate_history(history, settings.chat_history_max_chars)

    # Build a contextualized query: prepend last few assistant turns so follow-up
    # questions like "explain that" embed to meaningful content rather than near-zero.
    retrieval_query = body.question
    prior_assistant_turns = [
        t.statement for t in history
        if t.user_type == "assistant"
    ][-settings.retrieval_history_context_turns:]
    if prior_assistant_turns:
        prior_context = " ".join(prior_assistant_turns)
        retrieval_query = f"[Prior context: {prior_context}] {body.question}"

    # Derive file scope from the conversation type — client cannot override this
    match convo.conversation_type:
        case "per_file":
            if convo.file_id is None:
                raise HTTPException(status_code=422, detail="Associated file no longer exists.")
            file_ids = [convo.file_id]
        case _:  # global
            file_ids = None

    contexts = retrieve(
        query=retrieval_query,
        user_id=convo.user_id,
        db=db,
        file_ids=file_ids,
        top_k=body.top_k,
        use_summary_routing=body.use_summary_routing,
        use_bm25=body.use_bm25,
        use_propositions=body.use_propositions,
    )

    messages = [SystemMessage(content=_system_prompt(contexts))]
    for turn in history:
        if turn.user_type == "user":
            messages.append(HumanMessage(content=turn.statement))
        else:
            messages.append(AIMessage(content=turn.statement))
    messages.append(HumanMessage(content=body.question))

    answer: str = llm.invoke(messages).content

    db.add(Conversation(chat_id=conversation_id, user_type="user", statement=body.question))
    db.add(Conversation(chat_id=conversation_id, user_type="assistant", statement=answer))
    db.commit()

    # Only include citations whose [N] marker actually appears in the answer.
    referenced = {int(m) for m in _CITATION_RE.findall(answer)}
    citations = [
        Citation(
            file_id=c.file_id,
            filename=c.filename,
            page_start=c.page_start,
            page_end=c.page_end,
            content_preview=c.content[:300],
        )
        for i, c in enumerate(contexts, start=1)
        if i in referenced
    ]

    return AskResponse(answer=answer, citations=citations, conversation_id=conversation_id)
