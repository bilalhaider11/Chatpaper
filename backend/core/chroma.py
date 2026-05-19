from typing import Optional

import chromadb
from chromadb import Collection

from core.config import settings

_chroma_client: Optional[chromadb.HttpClient] = None


def get_chroma_client() -> chromadb.HttpClient:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
        )
    return _chroma_client


def get_child_chunks_collection() -> Collection:
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=settings.chroma_collection_child_chunks,
        metadata={"hnsw:space": "cosine"},
    )


def get_document_summaries_collection() -> Collection:
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=settings.chroma_collection_summaries,
        metadata={"hnsw:space": "cosine"},
    )


def reset_chroma_client() -> None:  # test helper only
    global _chroma_client
    _chroma_client = None
