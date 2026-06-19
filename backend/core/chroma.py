import logging
from typing import Optional

import chromadb
from chromadb import Collection

from core.config import settings
from core.llm import get_embedding_dimension

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


def _collection_embedding_dimension(col: Collection) -> int | None:
    meta_dim = (col.metadata or {}).get("embedding_dimension")
    if meta_dim is not None:
        return int(meta_dim)
    if col.count() == 0:
        return None
    peek = col.peek(limit=1, include=["embeddings"])
    embeddings = peek.get("embeddings") or []
    if embeddings and embeddings[0] is not None:
        return len(embeddings[0])
    return None


def _collection_needs_recreate(col: Collection, expected_dim: int) -> bool:
    stored_dim = (col.metadata or {}).get("embedding_dimension")
    if stored_dim is not None and int(stored_dim) != expected_dim:
        return True

    actual_dim = _collection_embedding_dimension(col)
    if actual_dim is not None and actual_dim != expected_dim:
        return True

    # Legacy collections created before we tagged embedding_dimension.
    if stored_dim is None and col.count() > 0:
        return True

    return False


def _ensure_collection(name: str, base_metadata: dict) -> Collection:
    """Get or create a collection, recreating it when the embedding dimension changed."""
    expected_dim = get_embedding_dimension()
    metadata = {**base_metadata, "embedding_dimension": expected_dim}
    client = get_chroma_client()

    try:
        col = client.get_collection(name)
        if _collection_needs_recreate(col, expected_dim):
            logger.warning(
                "Recreating Chroma collection %s for embedding dimension %s (was %s)",
                name,
                expected_dim,
                _collection_embedding_dimension(col),
            )
            client.delete_collection(name)
            return client.create_collection(name=name, metadata=metadata)
        return col
    except Exception:
        logger.info("Creating Chroma collection %s (dim=%s)", name, expected_dim)
        return client.create_collection(name=name, metadata=metadata)


def _fetch_collection(name: str, metadata: dict) -> Collection:
    """Get or create a collection, retrying once after a connection error."""
    try:
        return _ensure_collection(name, metadata)#openai
    except Exception:
        logger.warning("ChromaDB error fetching collection %s; resetting and retrying", name)
        _reset_all()
        return _ensure_collection(name, metadata)#openai


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
