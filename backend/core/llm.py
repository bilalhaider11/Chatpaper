from __future__ import annotations

import asyncio
import functools
import os

from dotenv import load_dotenv
import requests
from sentence_transformers import SentenceTransformer
from pydantic import BaseModel, model_validator

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
except ImportError:
    ChatOpenAI = None  # type: ignore[assignment,misc]
    OpenAIEmbeddings = None  # type: ignore[assignment,misc]

from core.config import settings

_embedder: "OpenAIEmbeddings | HFEmbedder" = None

if HF_API_KEY:
    os.environ.setdefault("HF_TOKEN", HF_API_KEY)


class _LLMResult:
    def __init__(self, content: str):
        self.content = content


class _LLMChunk:
    def __init__(self, content: str):
        self.content = content


def _normalize_messages(messages) -> list[dict[str, str]]:
    if isinstance(messages, str):
        return [{"role": "user", "content": messages}]

    openai_messages: list[dict[str, str]] = []
    for msg in messages:
        role = getattr(msg, "type", None) or getattr(msg, "role", "user")
        content = getattr(msg, "content", str(msg))
        
        if role in ("human", "user"):
            openai_messages.append({"role": "user", "content": content})
        elif role in ("ai", "assistant"):
            openai_messages.append({"role": "assistant", "content": content})
        else:
            openai_messages.append({"role": "user", "content": content})
    return openai_messages


class HuggingFaceChatLLM:
    def __init__(self, temperature: float = 0.2):
        self.temperature = temperature

    def _call_api(self, messages) -> str:
        headers = {
            "Authorization": f"Bearer {HF_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": HF_CHAT_MODEL,
            "messages": _normalize_messages(messages),
            "temperature": self.temperature,
            "max_tokens": 512,
        }
        response = requests.post(HF_ROUTER_CHAT_URL, headers=headers, json=payload, timeout=120)
        if response.status_code != 200:
            raise RuntimeError(f"HF API error ({response.status_code}): {response.text}")

        data = response.json()
        if "error" in data:
            err = data["error"]
            message = err.get("message", err) if isinstance(err, dict) else err
            raise RuntimeError(f"HF API error: {message}")

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"HF API returned no choices: {data}")

        message = choices[0].get("message") or {}
        content = message.get("content", "")
        if not content and message.get("reasoning"):
            content = message["reasoning"]
        return content.strip()

    def invoke(self, messages) -> _LLMResult:
        return _LLMResult(self._call_api(messages))

    async def ainvoke(self, messages) -> _LLMResult:
        return await asyncio.to_thread(self.invoke, messages)

    async def astream(self, messages):
        result = await self.ainvoke(messages)
        text = result.content
        chunk_size = 12
        for i in range(0, len(text), chunk_size):
            yield _LLMChunk(text[i : i + chunk_size])



class HFEmbedder:
    def __init__(self):
        self.model = SentenceTransformer(HF_EMBEDDING_MODEL)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, normalize_embeddings=True).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.model.encode([text], normalize_embeddings=True)[0].tolist()

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self.embed_documents, texts)

    async def aembed_query(self, text: str) -> list[float]:
        return await asyncio.to_thread(self.embed_query, text)


@functools.lru_cache(maxsize=8)
def get_chat_llm(temperature: float = 0.2) -> "HuggingFaceChatLLM | ChatOpenAI":
    if select_model == "HF":
        return HuggingFaceChatLLM(temperature=temperature)
    else:
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


def get_embedder() -> "HFEmbedder | OpenAIEmbeddings":
    global _embedder
    
    if select_model == "HF":
        if HF_EMBEDDING_MODEL:
            _embedder = HFEmbedder()
        else:
            raise RuntimeError("HF embedding model is not configured")
    else:
        if OpenAIEmbeddings is None:
            raise RuntimeError("langchain_openai is not installed")
        if _embedder is None:
            _embedder = OpenAIEmbeddings(
                model=settings.openai_embedding_model,
                api_key=settings.openai_api_key,
            )
            
    return _embedder
