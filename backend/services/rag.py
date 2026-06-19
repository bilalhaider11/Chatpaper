from __future__ import annotations

import dataclasses
import re

try:
    import tiktoken as _tiktoken
except ImportError:
    _tiktoken = None  # type: ignore[assignment]

try:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
except ImportError:
    AIMessage = None  # type: ignore[assignment,misc]
    HumanMessage = None  # type: ignore[assignment,misc]
    SystemMessage = None  # type: ignore[assignment,misc]

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.llm import get_chat_llm
from models.conversation import Conversation
from schema.chat import Citation
from services.retrieval import RetrievedContext, retrieve

_CITATION_RE = re.compile(r"\[(\d+)\]")


@dataclasses.dataclass(frozen=True, slots=True)
class _HistoryTurn:
    user_type: str
    statement: str

_PROMPT_HEADER = (
    "You are a research assistant. Answer using ONLY the document context below. "
    "Do NOT use your general knowledge — if the answer is not explicitly in the context, "
    "tell the user the information is not available in their documents. "
    "Cite sources with [N] notation matching the context numbers.\n\n"
    "Document context:\n\n"
)
_PROMPT_HEADER_NO_CTX = (
    "You are a research assistant that answers ONLY from the content of uploaded documents. "
    "No relevant content was found in the uploaded document(s) for this query. "
    "You MUST tell the user that this information is not available in their documents. "
    "Do NOT answer from your general knowledge under any circumstances."
)


def _count_tokens(text: str) -> int:
    if _tiktoken is None:
        return len(text) // 4
    try:
        enc = _tiktoken.encoding_for_model(settings.openai_chat_model)
    except KeyError:
        enc = _tiktoken.get_encoding("o200k_base")
    return len(enc.encode(text))


def _context_block(ctx: RetrievedContext, index: int) -> str:
    pages = f"pages {ctx.page_start}–{ctx.page_end}" if ctx.page_start else "page unknown"
    return f"[{index}] {ctx.filename} ({pages})\n{ctx.content}"


def _system_prompt(contexts: list[RetrievedContext]) -> str:
    if not contexts:
        return _PROMPT_HEADER_NO_CTX
    budget = settings.chat_max_context_tokens - _count_tokens(_PROMPT_HEADER)
    selected: list[str] = []
    used = 0
    for i, ctx in enumerate(contexts):
        block = _context_block(ctx, i + 1)
        tokens = _count_tokens(block)
        if used + tokens > budget:
            break
        selected.append(block)
        used += tokens
    # Always include at least the top context even if it alone exceeds the budget.
    if not selected:
        selected = [_context_block(contexts[0], 1)]
    return _PROMPT_HEADER + "\n\n---\n\n".join(selected)


def _truncate_history(history: list[_HistoryTurn], max_chars: int) -> list[_HistoryTurn]:
    while history:
        total = sum(len(turn.statement) for turn in history)
        if total <= max_chars:
            break
        history = history[1:]
    return history


def _materialize_history(messages: list) -> list[_HistoryTurn]:
    """Copy ORM rows to plain values before retrieval (retrieve may rollback the session)."""
    return [
        _HistoryTurn(user_type=turn.user_type, statement=turn.statement)
        for turn in messages
    ]


def extract_citations(answer: str, contexts: list[RetrievedContext]) -> list[Citation]:
    referenced = {int(m) for m in _CITATION_RE.findall(answer)}
    return [
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


async def prepare(
    question: str,
    convo,  # ConversationList ORM object or SimpleNamespace with .id .conversation_type .file_id .user_id
    db: AsyncSession,
    top_k: int = 5,
    use_summary_routing: bool = True,
    use_bm25: bool = True,
    use_propositions: bool = False,
) -> tuple[list, list[RetrievedContext]]:
    """Fetch history, retrieve context, build LangChain messages list."""
    from services.conversation import get_merged_messages

    all_history = await get_merged_messages(convo.id, db)
    history = _truncate_history(
        _materialize_history(all_history[-settings.chat_history_turns :]),
        settings.chat_history_max_chars,
    )
    match convo.conversation_type:
        case "per_file":
            file_ids = [convo.file_id] if convo.file_id else None
            # Per-file only: prior context is safe because file_ids locks retrieval to one doc.
            # Global skips this — off-topic prior responses bias the embedding across files.
            prior_assistant = [t.statement for t in history if t.user_type == "assistant"][
                -settings.retrieval_history_context_turns:
            ]
            retrieval_query = (
                f"[Prior context: {' '.join(prior_assistant)}] {question}"
                if prior_assistant else question
            )
        case _:
            file_ids = None
            retrieval_query = question

    contexts = await retrieve(
        query=retrieval_query,
        user_id=convo.user_id,
        conversation_type=convo.conversation_type,
        conversationlist_id=convo.id,
        db=db,
        file_ids=file_ids,
        top_k=top_k,
        use_summary_routing=use_summary_routing,
        use_bm25=use_bm25,
        use_propositions=use_propositions,
    )

    messages = [SystemMessage(content=_system_prompt(contexts))]
    for turn in history:
        if turn.user_type == "user":
            messages.append(HumanMessage(content=turn.statement))
        else:
            messages.append(AIMessage(content=turn.statement))
    messages.append(HumanMessage(content=question))

    return messages, contexts


async def run_rag(
    question: str,
    convo,
    db: AsyncSession,
    top_k: int = 5,
    use_summary_routing: bool = True,
    use_bm25: bool = True,
    use_propositions: bool = False,
) -> tuple[str, list[Citation]]:
    """Blocking RAG — used by the HTTP /ask endpoint."""
    llm = get_chat_llm(temperature=0.2)
    messages, contexts = await prepare(
        question, convo, db, top_k, use_summary_routing, use_bm25, use_propositions
    )
    answer: str = (await llm.ainvoke(messages)).content
    return answer, extract_citations(answer, contexts)
