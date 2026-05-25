from typing import Optional

import chromadb
from chromadb import Collection

from core.config import settings

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


def get_child_chunks_collection() -> Collection:
    global _child_chunks_col
    if _child_chunks_col is None:
        _child_chunks_col = get_chroma_client().get_or_create_collection(
            name=settings.chroma_collection_child_chunks,
            metadata={"hnsw:space": "cosine"},
        )
    return _child_chunks_col


def get_document_summaries_collection() -> Collection:
    global _summaries_col
    if _summaries_col is None:
        _summaries_col = get_chroma_client().get_or_create_collection(
            name=settings.chroma_collection_summaries,
            metadata={"hnsw:space": "cosine"},
        )
    return _summaries_col


def get_propositions_collection() -> Collection:
    global _propositions_col
    if _propositions_col is None:
        _propositions_col = get_chroma_client().get_or_create_collection(
            name=settings.chroma_collection_propositions,
            metadata={"hnsw:space": "cosine"},
        )
    return _propositions_col


def delete_vectors_for_file(file_id: int, user_id: int) -> None:
    where = {"$and": [{"file_id": file_id}, {"user_id": user_id}]}
    get_child_chunks_collection().delete(where=where)
    get_document_summaries_collection().delete(where=where)
    get_propositions_collection().delete(where=where)


def reset_chroma_client() -> None:  # test helper only
    global _chroma_client
    _chroma_client = None


def reset_chroma_collections() -> None:  # test helper only
    global _child_chunks_col, _summaries_col, _propositions_col
    _child_chunks_col = None
    _summaries_col = None
    _propositions_col = None
