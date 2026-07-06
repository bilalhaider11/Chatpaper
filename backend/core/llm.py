from __future__ import annotations
import functools
import os
from dotenv import load_dotenv
from core.config import settings

load_dotenv()

select_model = os.getenv("SELECT_MODEL", "HF")


HF_API_KEY = settings.HF_API_KEY
# Legacy api-inference.huggingface.co is retired; use the router chat API.
HF_CHAT_MODEL = settings.HF_CHAT_MODEL
HF_ROUTER_CHAT_URL = settings.HF_ROUTER_CHAT_URL
HF_EMBEDDING_MODEL = settings.HF_EMBEDDING_MODEL
EMBEDDING_DIMENSION = settings.EMBEDDING_DIMENSION

try:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from langchain_huggingface import (
        ChatHuggingFace,
        HuggingFaceEndpoint,
        HuggingFaceEmbeddings,
    )
except ImportError:
    ChatOpenAI = None  # type: ignore[assignment,misc]
    OpenAIEmbeddings = None  # type: ignore[assignment,misc]
    ChatHuggingFace = None
    HuggingFaceEndpoint = None
    HuggingFaceEmbeddings = None


_embedder: "OpenAIEmbeddings | HuggingFaceEmbeddings" = None



@functools.lru_cache(maxsize=8)
def get_chat_llm(temperature: float = 0.2):
    if select_model == "HF":
        if HuggingFaceEndpoint is None:
            raise RuntimeError("langchain_openai is not installed")
        llm = HuggingFaceEndpoint(
            repo_id=HF_CHAT_MODEL,
            huggingfacehub_api_token=HF_API_KEY,
            task="text-generation",
            temperature=temperature,
            max_new_tokens=512,
        )

        return ChatHuggingFace(llm=llm)

    if ChatOpenAI is None:
        raise RuntimeError("langchain_openai is not installed")

    return ChatOpenAI(
        model=settings.openai_chat_model,
        temperature=temperature,
        api_key=settings.openai_api_key,
    )

def get_embedding_model_name() -> str:
    if select_model == "HF":
        return HF_EMBEDDING_MODEL
    return settings.openai_embedding_model

def get_embedder():
    global _embedder

    if _embedder is not None:
        return _embedder

    if select_model == "HF":
        _embedder = HuggingFaceEmbeddings(
            model_name=HF_EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    else:
        if OpenAIEmbeddings is None:
            raise RuntimeError("langchain_openai is not installed")

        _embedder = OpenAIEmbeddings(
            model=settings.openai_embedding_model,
            api_key=settings.openai_api_key,
        )

    return _embedder