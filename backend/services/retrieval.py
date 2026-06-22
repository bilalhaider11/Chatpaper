from __future__ import annotations

import dataclasses
import logging

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.chroma import (
    get_child_chunks_collection,
    get_document_summaries_collection,
    get_propositions_collection,
)
from core.config import settings
from core.llm import get_embedder
from models.file_model import FileRecord
from models.conversation import ConversationList,CombinedSharedConversationImport
from models.ingestion import DocumentParent

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class RetrievedContext:
    parent_id: str
    content: str
    file_id: int
    filename: str
    page_start: int | None
    page_end: int | None
    element_types: list[str]
    score: float  # RRF fused score


async def _owner_ids_for_files(file_ids: list[int], db: AsyncSession) -> list[int]:
    result = await db.execute(
        select(FileRecord.user_id).where(
            FileRecord.id.in_(file_ids),
            FileRecord.is_active == True,  # noqa: E712
        )
    )
    return list(set(result.scalars().all()))

async def all_files_when_shared_global(user_id:int, conversationlist_id:int,db: AsyncSession) ->list[int]:

    result = await db.execute(
        select(ConversationList.file_id)
        .where(
            ConversationList.user_id
            == (
                select(CombinedSharedConversationImport.shared_user_id)
                .where(
                    CombinedSharedConversationImport.id
                    == (
                        select(ConversationList.shared_conversation_id)
                        .where(ConversationList.id == conversationlist_id)
                        .scalar_subquery()
                    )
                )
                .scalar_subquery()
            ),
            ConversationList.file_id.is_not(None),
            ConversationList.is_active == True,
        )
    )
    
    return list(set(result.scalars().all()))
    

async def _global_accessible_file_ids(user_id: int, db: AsyncSession) -> list[int]:
    """File IDs from the user's own per-file chats and imported shared chats."""
    result = await db.execute(
        select(ConversationList.file_id).where(
            ConversationList.user_id == user_id,
            ConversationList.is_active == True,  # noqa: E712
            ConversationList.file_id.is_not(None),
        )
    )
    candidate_file_ids = list(set({fid for fid in result.scalars().all() if fid is not None}))
    if not candidate_file_ids:
        return []

    return candidate_file_ids

async def _resolve_retrieval_scope(
    user_id: int,
    conversation_type:str,
    conversationlist_id:int,
    file_ids: list[int] | None,
    db: AsyncSession,
) -> tuple[list[int], list[int] | None]:
    """Return Chroma owner user IDs and scoped file IDs for retrieval.

    file_ids=None means global scope: own uploads plus files from imported
    shared chats. An explicit empty list means no accessible documents.
    """

    if file_ids is None and conversation_type == "global":
        scoped_file_ids = await _global_accessible_file_ids(user_id, db)
    elif file_ids is None and conversation_type =="shared global":
        scoped_file_ids = await all_files_when_shared_global(user_id,conversationlist_id, db)
    else:
        scoped_file_ids = file_ids

    if not scoped_file_ids:
        return [user_id], scoped_file_ids

    owner_ids = await _owner_ids_for_files(scoped_file_ids, db)

    return owner_ids or [user_id], scoped_file_ids


def _where(user_ids: list[int], file_ids: list[int] | None) -> dict:
    filters = [{"user_id": {"$in": user_ids}}]

    if file_ids:
        filters.append({"file_id": {"$in": file_ids}})

    if len(filters) == 1:
        return filters[0]

    return {"$and": filters}


def _chroma_query(collection, query_embedding: list[float], where: dict, n: int) -> dict:
    try:
        return collection.query(
            query_embeddings=[query_embedding],
            n_results=n,
            where=where,
            include=["metadatas", "distances"],
        )
    except Exception:
        logger.exception("ChromaDB query failed")
        return {"metadatas": [[]], "distances": [[]]}


def _collection_retrieve(
    collection,
    query_embedding: list[float],
    user_ids: list[int],
    file_ids: list[int] | None,
    n: int,
) -> dict[str, float]:
    results = _chroma_query(collection, query_embedding, _where(user_ids, file_ids), n)
    parent_scores: dict[str, float] = {}
    for meta, dist in zip(results["metadatas"][0], results["distances"][0]):
        pid = meta.get("parent_id")
        if not pid:
            continue
        sim = 1.0 - dist  # cosine distance = 1 - similarity in ChromaDB
        if pid not in parent_scores or sim > parent_scores[pid]:
            parent_scores[pid] = sim
    return parent_scores


def _dense_retrieve(
    query_embedding: list[float],
    user_ids: list[int],
    file_ids: list[int] | None,
    n: int,
) -> dict[str, float]:
    return _collection_retrieve(get_child_chunks_collection(), query_embedding, user_ids, file_ids, n)


def _proposition_retrieve(
    query_embedding: list[float],
    user_ids: list[int],
    file_ids: list[int] | None,
    n: int,
) -> dict[str, float]:
    return _collection_retrieve(get_propositions_collection(), query_embedding, user_ids, file_ids, n)


def _summary_route(
    query_embedding: list[float],
    user_ids: list[int],
    file_ids: list[int] | None,
    n_files: int,
) -> list[int] | None:
    results = _chroma_query(
        get_document_summaries_collection(),
        query_embedding,
        _where(user_ids, file_ids),
        n_files,
    )
    metas = results["metadatas"][0]
    if not metas:
        return None
    return [int(m["file_id"]) for m in metas]


async def _bm25_retrieve(
    query: str,
    user_ids: list[int],
    file_ids: list[int] | None,
    db: AsyncSession,
    n: int,
) -> dict[str, float]:
    params: dict = {"query": query, "user_id": user_ids, "limit": n}
    file_filter = ""
    if file_ids:
        file_filter = "AND dp.file_id = ANY(:file_ids)"
        params["file_ids"] = file_ids

    sql = text(f"""
        SELECT dp.id,
               ts_rank(to_tsvector('english', dp.content),
                       plainto_tsquery('english', :query)) AS rank
        FROM document_parents dp
        JOIN files_data fd ON dp.file_id = fd.id
        WHERE fd.user_id = ANY(:user_ids)
          AND fd."is_Active" = TRUE
          AND to_tsvector('english', dp.content)
              @@ plainto_tsquery('english', :query)
          {file_filter}
        ORDER BY rank DESC
        LIMIT :limit
    """)
    try:
        result = await db.execute(sql, params)
        rows = result.fetchall()
    except Exception:
        logger.exception("BM25 retrieval failed")
        # Roll back the aborted transaction so subsequent queries on this session still work
        await db.rollback()
        return {}
    return {row.id: float(row.rank) for row in rows}


def _rrf(ranked_lists: list[list[str]], k: int = 60) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, pid in enumerate(ranked):
            scores[pid] = scores.get(pid, 0.0) + 1.0 / (k + rank + 1)
    return scores


async def retrieve(
    query: str,
    user_id: int,
    conversation_type:str,
    conversationlist_id:int,
    db: AsyncSession,
    file_ids: list[int] | None = None,
    top_k: int = 5,
    use_summary_routing: bool = True,
    use_bm25: bool = True,
    use_propositions: bool = False,
) -> list[RetrievedContext]:
    embedder = get_embedder()
    query_embedding = await embedder.aembed_query(query)
    vector_user_id, scoped_file_ids = await _resolve_retrieval_scope(user_id,conversation_type, conversationlist_id,file_ids, db)
    if scoped_file_ids is not None and not scoped_file_ids:
        return []

    # narrow the child chunk search to files that match the query at the document level
    routing_file_ids = scoped_file_ids
    if use_summary_routing:
        routed = _summary_route(query_embedding, vector_user_id, scoped_file_ids, n_files=10)
        if routed:
            routing_file_ids = routed

    fetch_n = top_k * 4
    ranked_lists: list[list[str]] = []

    dense_scores = _dense_retrieve(query_embedding, vector_user_id, routing_file_ids, fetch_n)
    if dense_scores:
        ranked_lists.append(sorted(dense_scores, key=lambda p: dense_scores[p], reverse=True))

    if use_bm25:
        bm25_scores = await _bm25_retrieve(query, vector_user_id, routing_file_ids, db, fetch_n)
        if bm25_scores:
            ranked_lists.append(sorted(bm25_scores, key=lambda p: bm25_scores[p], reverse=True))

    if use_propositions:
        prop_scores = _proposition_retrieve(query_embedding, vector_user_id, routing_file_ids, fetch_n)
        if prop_scores:
            ranked_lists.append(sorted(prop_scores, key=lambda p: prop_scores[p], reverse=True))

    if not ranked_lists:
        return []

    fused = _rrf(ranked_lists)
    min_score = settings.retrieval_min_score
    top_ids = [
        p for p in sorted(fused, key=lambda p: fused[p], reverse=True)
        if fused[p] >= min_score
    ][:top_k]

    parent_query = (
        select(DocumentParent, FileRecord.filename)
        .join(FileRecord, DocumentParent.file_id == FileRecord.id)
        .where(
            DocumentParent.id.in_(top_ids),
            DocumentParent.file_id.in_(scoped_file_ids),
            FileRecord.is_active == True,  # noqa: E712
        )
    )
    result = await db.execute(parent_query)
    rows = result.all()

    parent_map = {dp.id: (dp, fname) for dp, fname in rows}
    results: list[RetrievedContext] = []
    for pid in top_ids:
        if pid not in parent_map:
            continue
        dp, fname = parent_map[pid]
        results.append(RetrievedContext(
            parent_id=pid,
            content=dp.content,
            file_id=dp.file_id,
            filename=fname,
            page_start=dp.page_start,
            page_end=dp.page_end,
            element_types=dp.element_types or [],
            score=fused[pid],
        ))

    return results
