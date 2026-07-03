import logging
from typing import Optional

import chromadb
from chromadb import Collection

from core.config import settings

logger = logging.getLogger(__name__)

_chroma_client: Optional[chromadb.HttpClient] = None
_child_chunks_col: Optional[Collection] = None
_summaries_col: Optional[Collection] = None
_propositions_col: Optional[Collection] = None


def get_chroma_client() -> chromadb.HttpClient:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
        )
    return _chroma_client


def _reset_all() -> None:
    """Clear all cached handles so the next access re-connects. Call after any ChromaDB error."""
    global _chroma_client, _child_chunks_col, _summaries_col, _propositions_col
    _chroma_client = None
    _child_chunks_col = None
    _summaries_col = None
    _propositions_col = None


def _fetch_collection(name: str, metadata: dict) -> Collection:
    """Get or create a collection, retrying once after a connection error."""
    try:
        return get_chroma_client().get_or_create_collection(name=name, metadata=metadata)
    except Exception:
        logger.warning("ChromaDB error fetching collection %s; resetting and retrying", name)
        _reset_all()
        return get_chroma_client().get_or_create_collection(name=name, metadata=metadata)


def get_child_chunks_collection() -> Collection:
    global _child_chunks_col
    if _child_chunks_col is None:
        _child_chunks_col = _fetch_collection(
            settings.chroma_collection_child_chunks, {"hnsw:space": "cosine"}
        )
    return _child_chunks_col


def get_document_summaries_collection() -> Collection:
    global _summaries_col
    if _summaries_col is None:
        _summaries_col = _fetch_collection(
            settings.chroma_collection_summaries, {"hnsw:space": "cosine"}
        )
    return _summaries_col


def get_propositions_collection() -> Collection:
    global _propositions_col
    if _propositions_col is None:
        _propositions_col = _fetch_collection(
            settings.chroma_collection_propositions, {"hnsw:space": "cosine"}
        )
    return _propositions_col


def delete_vectors_for_file(file_id: int, user_id: int) -> None:
    where = {"$and": [{"file_id": file_id}, {"user_id": user_id}]}
    try:
        get_child_chunks_collection().delete(where=where)
        get_document_summaries_collection().delete(where=where)
        get_propositions_collection().delete(where=where)
    except Exception:
        # Stale handle — reset and retry once so a ChromaDB restart doesn't leave orphaned vectors.
        _reset_all()
        get_child_chunks_collection().delete(where=where)
        get_document_summaries_collection().delete(where=where)
        get_propositions_collection().delete(where=where)


def reset_chroma_client() -> None:
    global _chroma_client
    _chroma_client = None


def reset_chroma_collections() -> None:
    global _child_chunks_col, _summaries_col, _propositions_col
    _child_chunks_col = None
    _summaries_col = None
    _propositions_col = None
