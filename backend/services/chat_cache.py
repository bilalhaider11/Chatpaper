import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from core.config import settings
from core.redis_client import get_redis

logger = logging.getLogger(__name__)

FLUSH_QUEUE_KEY = "chat:flush:queue"

# Atomically reads and clears the flush queue in a single round-trip,
# preventing message loss from concurrent drain calls (TOCTOU between LRANGE + DEL).
_DRAIN_QUEUE_SCRIPT = (
    "local i=redis.call('LRANGE',KEYS[1],0,-1) "
    "if #i>0 then redis.call('DEL',KEYS[1]) end "
    "return i"
)

# Registered script handle (uses EVALSHA for efficiency); populated lazily on first use.
_drain_script = None


@dataclass
class QueuedChatMessage:
    chat_id: int
    user_type: str
    statement: str
    temp_id: str | None = None
    enqueued_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _pending_key(chat_id: int) -> str:
    return f"chat:pending:{chat_id}"


def _stream_key(chat_id: int, temp_id: str) -> str:
    return f"chat:stream:{chat_id}:{temp_id}"


def _message_to_json(message: QueuedChatMessage) -> str:
    return json.dumps(asdict(message))


def _message_from_json(raw: str) -> QueuedChatMessage:
    data = json.loads(raw)
    return QueuedChatMessage(
        chat_id=int(data["chat_id"]),
        user_type=data["user_type"],
        statement=data["statement"],
        temp_id=data.get("temp_id"),
        enqueued_at=data.get("enqueued_at", ""),
    )


_MAX_IN_MEMORY_STREAMS = 500


class InMemoryChatCache:
    def __init__(self) -> None:
        self._flush_queue: list[str] = []
        self._pending: dict[int, list[str]] = {}
        self._streams: dict[str, str] = {}  # ordered dict; oldest key evicted at _MAX_IN_MEMORY_STREAMS

    async def enqueue(self, message: QueuedChatMessage) -> None:
        payload = _message_to_json(message)
        self._flush_queue.append(payload)
        self._pending.setdefault(message.chat_id, []).append(payload)

    async def drain_flush_queue(self) -> list[QueuedChatMessage]:
        payloads = self._flush_queue[:]
        self._flush_queue.clear()
        messages = [_message_from_json(item) for item in payloads]
        for msg in messages:
            serialized = _message_to_json(msg)
            pending = self._pending.get(msg.chat_id, [])
            if serialized in pending:
                pending.remove(serialized)
        return messages

    async def flush_queue_size(self) -> int:
        return len(self._flush_queue)

    async def get_pending(self, chat_id: int) -> list[QueuedChatMessage]:
        return [_message_from_json(item) for item in self._pending.get(chat_id, [])]

    async def append_stream_chunk(self, chat_id: int, temp_id: str, chunk: str) -> None:
        key = _stream_key(chat_id, temp_id)
        if key not in self._streams and len(self._streams) >= _MAX_IN_MEMORY_STREAMS:
            # Evict the oldest stream (insertion-ordered dict).
            self._streams.pop(next(iter(self._streams)), None)
        self._streams[key] = self._streams.get(key, "") + chunk

    async def get_active_streams(self, chat_id: int) -> list[dict]:
        prefix = f"chat:stream:{chat_id}:"
        results: list[dict] = []
        for key, statement in self._streams.items():
            if not key.startswith(prefix):
                continue
            temp_id = key.removeprefix(prefix)
            results.append(
                {
                    "temp_id": temp_id,
                    "user_type": "assistant",
                    "statement": statement,
                    "streaming": True,
                }
            )
        return results

    async def clear_stream(self, chat_id: int, temp_id: str) -> None:
        self._streams.pop(_stream_key(chat_id, temp_id), None)


_memory_cache = InMemoryChatCache()


async def enqueue_message(message: QueuedChatMessage) -> None:
    redis_client = get_redis()
    payload = _message_to_json(message)

    if redis_client is None:
        await _memory_cache.enqueue(message)
        return

    pipe = redis_client.pipeline()
    pipe.rpush(FLUSH_QUEUE_KEY, payload)
    pipe.expire(FLUSH_QUEUE_KEY, settings.chat_data_ttl_seconds)
    pending_key = _pending_key(message.chat_id)
    pipe.rpush(pending_key, payload)
    pipe.expire(pending_key, settings.chat_data_ttl_seconds)
    await pipe.execute()


def _streamset_key(chat_id: int) -> str:
    return f"chat:streamset:{chat_id}"


async def drain_flush_queue() -> list[QueuedChatMessage]:
    global _drain_script
    redis_client = get_redis()
    if redis_client is None:
        return await _memory_cache.drain_flush_queue()

    if _drain_script is None:
        _drain_script = redis_client.register_script(_DRAIN_QUEUE_SCRIPT)

    payloads = await _drain_script(keys=[FLUSH_QUEUE_KEY])
    if not payloads:
        return []

    messages = [_message_from_json(item) for item in payloads]

    pipe = redis_client.pipeline()
    for msg in messages:
        pipe.lrem(_pending_key(msg.chat_id), 1, _message_to_json(msg))
    await pipe.execute()
    return messages


async def flush_queue_size() -> int:
    redis_client = get_redis()
    if redis_client is None:
        return await _memory_cache.flush_queue_size()
    return int(await redis_client.llen(FLUSH_QUEUE_KEY))


async def get_pending_messages(chat_id: int) -> list[QueuedChatMessage]:
    redis_client = get_redis()
    if redis_client is None:
        return await _memory_cache.get_pending(chat_id)

    payloads = await redis_client.lrange(_pending_key(chat_id), 0, -1)
    return [_message_from_json(item) for item in payloads]


async def append_stream_chunk(chat_id: int, temp_id: str, chunk: str) -> None:
    redis_client = get_redis()
    if redis_client is None:
        await _memory_cache.append_stream_chunk(chat_id, temp_id, chunk)
        return

    key = _stream_key(chat_id, temp_id)
    sset = _streamset_key(chat_id)
    pipe = redis_client.pipeline()
    pipe.append(key, chunk)
    pipe.expire(key, settings.chat_stream_ttl_seconds)
    # Track this stream key in a SET so get_active_streams avoids SCAN.
    pipe.sadd(sset, key)
    pipe.expire(sset, settings.chat_stream_ttl_seconds)
    await pipe.execute()


async def get_active_streams(chat_id: int) -> list[dict]:
    redis_client = get_redis()
    if redis_client is None:
        return await _memory_cache.get_active_streams(chat_id)

    sset = _streamset_key(chat_id)
    keys = await redis_client.smembers(sset)
    if not keys:
        return []

    prefix = f"chat:stream:{chat_id}:"
    results: list[dict] = []
    dead_keys: list[str] = []
    for key in keys:
        statement = await redis_client.get(key)
        if not statement:
            dead_keys.append(key)
            continue
        temp_id = key.removeprefix(prefix)
        results.append({"temp_id": temp_id, "user_type": "assistant", "statement": statement, "streaming": True})

    if dead_keys:
        await redis_client.srem(sset, *dead_keys)

    return results


async def clear_stream(chat_id: int, temp_id: str) -> None:
    redis_client = get_redis()
    if redis_client is None:
        await _memory_cache.clear_stream(chat_id, temp_id)
        return
    key = _stream_key(chat_id, temp_id)
    pipe = redis_client.pipeline()
    pipe.delete(key)
    pipe.srem(_streamset_key(chat_id), key)
    await pipe.execute()
