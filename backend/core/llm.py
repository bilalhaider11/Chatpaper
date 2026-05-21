from __future__ import annotations

try:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
except ImportError:
    ChatOpenAI = None  # type: ignore[assignment,misc]
    OpenAIEmbeddings = None  # type: ignore[assignment,misc]

from core.config import settings


def get_embedder() -> "OpenAIEmbeddings":
    if OpenAIEmbeddings is None:
        raise RuntimeError("langchain_openai is not installed")
    return OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        api_key=settings.openai_api_key,
    )


def get_chat_llm(temperature: float = 0.2) -> "ChatOpenAI":
    if ChatOpenAI is None:
        raise RuntimeError("langchain_openai is not installed")
    return ChatOpenAI(
        model=settings.openai_chat_model,
        temperature=temperature,
        api_key=settings.openai_api_key,
    )
