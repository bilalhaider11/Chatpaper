from __future__ import annotations

import functools

try:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
except ImportError:
    ChatOpenAI = None  # type: ignore[assignment,misc]
    OpenAIEmbeddings = None  # type: ignore[assignment,misc]

from core.config import settings

_embedder: "OpenAIEmbeddings | None" = None


def get_embedder() -> "OpenAIEmbeddings":
    global _embedder
    if OpenAIEmbeddings is None:
        raise RuntimeError("langchain_openai is not installed")
    if _embedder is None:
        _embedder = OpenAIEmbeddings(
            model=settings.openai_embedding_model,
            api_key=settings.openai_api_key,
        )
    return _embedder


@functools.lru_cache(maxsize=8)
def get_chat_llm(temperature: float = 0.2) -> "ChatOpenAI":
    if ChatOpenAI is None:
        raise RuntimeError("langchain_openai is not installed")
    return ChatOpenAI(
        model=settings.openai_chat_model,
        temperature=temperature,
        api_key=settings.openai_api_key,
    )
