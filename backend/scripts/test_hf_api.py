#!/usr/bin/env python3
"""
Smoke-test Hugging Face chat API and local embedding model used by Chatpaper.

Usage:
    cd backend
    python scripts/test_hf_api.py

Docker:
    docker compose exec backend python scripts/test_hf_api.py
"""
from __future__ import annotations

import asyncio
import socket
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.llm import (
    HF_API_KEY,
    HF_CHAT_MODEL,
    HF_EMBEDDING_MODEL,
    HF_ROUTER_CHAT_URL,
    get_chat_llm,
    get_embedder,
)


def _ok(label: str, detail: str = "") -> None:
    suffix = f" — {detail}" if detail else ""
    print(f"✅ {label}{suffix}")


def _fail(label: str, detail: str = "") -> None:
    suffix = f" — {detail}" if detail else ""
    print(f"❌ {label}{suffix}")


def _warn(label: str, detail: str = "") -> None:
    suffix = f" — {detail}" if detail else ""
    print(f"⚠️  {label}{suffix}")


def test_dns_resolution() -> bool:
    print("--- Network / DNS ---")
    host = "router.huggingface.co"
    try:
        socket.getaddrinfo(host, 443)
        _ok("DNS resolves", host)
        return True
    except socket.gaierror as exc:
        _fail("DNS resolution", f"{host}: {exc}")
        _warn(
            "Docker DNS",
            "if only chat fails inside Docker, restart compose or add DNS (e.g. 8.8.8.8) to daemon.json",
        )
        return False


def test_hf_api_key_present() -> bool:
    if HF_API_KEY and HF_API_KEY.startswith("hf_"):
        _ok("HF API key configured", f"key ends with ...{HF_API_KEY[-4:]}")
        return True
    _fail("HF API key missing or invalid")
    return False


def test_hf_router_reachable() -> bool:
    try:
        response = requests.get("https://huggingface.co", timeout=15)
        if response.status_code == 200:
            _ok("Outbound HTTPS", "huggingface.co reachable")
            return True
        _fail("Outbound HTTPS", f"huggingface.co returned {response.status_code}")
        return False
    except Exception as exc:
        _fail("Outbound HTTPS", str(exc))
        return False


def test_hf_chat_api() -> bool:
    print(f"\n--- Chat API ({HF_CHAT_MODEL}) ---")
    print(f"Endpoint: {HF_ROUTER_CHAT_URL}")
    try:
        llm = get_chat_llm(temperature=0.2)
        result = llm.invoke([{"role": "user", "content": "Reply with exactly one word: hello"}])
        text = (result.content or "").strip()
        if not text:
            _fail("Chat API returned empty response")
            return False
        _ok("Chat API", f'response: "{text[:80]}"')
        return True
    except Exception as exc:
        _fail("Chat API", str(exc))
        return False


async def test_hf_chat_api_async() -> bool:
    print("\n--- Chat API async (ainvoke) ---")
    try:
        llm = get_chat_llm(temperature=0.2)
        result = await llm.ainvoke([{"role": "user", "content": "Say OK in one word."}])
        text = (result.content or "").strip()
        if not text:
            _fail("Async chat API returned empty response")
            return False
        _ok("Async chat API", f'response: "{text[:80]}"')
        return True
    except Exception as exc:
        _fail("Async chat API", str(exc))
        return False


def test_local_embeddings() -> bool:
    print(f"\n--- Embeddings ({HF_EMBEDDING_MODEL}, local) ---")
    try:
        embedder = get_embedder()
        vector = embedder.embed_query("Chatpaper retrieval smoke test")
        if not vector:
            _fail("Embedding returned empty vector")
            return False
        if len(vector) < 64:
            _fail("Embedding vector unexpectedly short", f"dim={len(vector)}")
            return False
        _ok("Local embeddings", f"dim={len(vector)}, sample={vector[0]:.4f}")
        return True
    except Exception as exc:
        _fail("Local embeddings", str(exc))
        return False


async def test_local_embeddings_async() -> bool:
    print("\n--- Embeddings async (aembed_query) ---")
    try:
        embedder = get_embedder()
        vector = await embedder.aembed_query("async embedding check")
        if not vector:
            _fail("Async embedding returned empty vector")
            return False
        _ok("Async embeddings", f"dim={len(vector)}")
        return True
    except Exception as exc:
        _fail("Async embeddings", str(exc))
        return False


async def main() -> int:
    print("Chatpaper Hugging Face / LLM smoke test\n")

    results = [
        test_dns_resolution(),
        test_hf_api_key_present(),
        test_hf_router_reachable(),
        test_hf_chat_api(),
        await test_hf_chat_api_async(),
        test_local_embeddings(),
        await test_local_embeddings_async(),
    ]

    passed = sum(results)
    total = len(results)
    print(f"\n{'=' * 40}")
    print(f"Result: {passed}/{total} checks passed")

    if passed == total:
        print("All checks passed.")
        return 0

    print("Some checks failed.")
    print("- Chat uses router.huggingface.co (api-inference.huggingface.co is retired).")
    print("- Ensure HF token has Inference Providers permission at https://huggingface.co/settings/tokens")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
