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
    created_at: datetime | None = None
    temp_id: str | None = None
    enqueued_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _pending_key(chat_id: int) -> str:
    return f"chat:pending:{chat_id}"


def _stream_key(chat_id: int, temp_id: str) -> str:
    return f"chat:stream:{chat_id}:{temp_id}"


def _normalize_created_at(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None


def _message_to_json(message: QueuedChatMessage) -> str:
    data = asdict(message)
    created_at = data.get("created_at")
    if isinstance(created_at, datetime):
        data["created_at"] = created_at.isoformat()
    return json.dumps(data)


def _message_from_json(raw: str) -> QueuedChatMessage:
    data = json.loads(raw)
    return QueuedChatMessage(
        chat_id=int(data["chat_id"]),
        user_type=data["user_type"],
        statement=data["statement"],
        temp_id=data.get("temp_id"),
        created_at=_normalize_created_at(data.get("created_at")),
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

    async def drain_flush_queue_for_chat(self, chat_id: int) -> list[QueuedChatMessage]:
        pending_payloads = self._pending.pop(chat_id, [])
        if not pending_payloads:
            return []

        pending_set = set(pending_payloads)
        self._flush_queue = [item for item in self._flush_queue if item not in pending_set]
        return [_message_from_json(item) for item in pending_payloads]

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
        for key, statement, created_at in self._streams.items():
            if not key.startswith(prefix):
                continue
            temp_id = key.removeprefix(prefix)
            results.append(
                {
                    "temp_id": temp_id,
                    "user_type": "assistant",
                    "statement": statement,
                    "created_at": created_at,
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


async def drain_flush_queue_for_chat(chat_id: int) -> list[QueuedChatMessage]:
    """Remove and return queued messages for one chat from flush and pending queues."""
    redis_client = get_redis()
    if redis_client is None:
        return await _memory_cache.drain_flush_queue_for_chat(chat_id)

    pending_key = _pending_key(chat_id)
    payloads = await redis_client.lrange(pending_key, 0, -1)
    if not payloads:
        return []

    pipe = redis_client.pipeline()
    for payload in payloads:
        pipe.lrem(FLUSH_QUEUE_KEY, 0, payload)
    pipe.delete(pending_key)
    await pipe.execute()
    return [_message_from_json(item) for item in payloads]


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


def _conversation_cache_key(chat_id: int) -> str:
    return f"chat:convo:{chat_id}:messages"


def _conversation_to_dict(message: dict) -> dict:
    
    # Extract the created_at value
    created_at = message.get("created_at")
    
    # Convert datetime object to string if it exists
    if isinstance(created_at, datetime):
        created_at = created_at.isoformat()

    return {
        "id": message.get("id"),
        "chat_id": message.get("chat_id"),
        "user_type": message["user_type"],
        "statement": message["statement"],
        "created_at": created_at,  # Now a JSON-safe string
    }

class InMemoryConversationCache:
    def __init__(self) -> None:
        self._messages: dict[int, list[dict]] = {}

    async def get_messages(self, chat_id: int) -> list[dict] | None:
        return self._messages.get(chat_id)

    async def set_messages(self, chat_id: int, messages: list[dict]) -> None:
        self._messages[chat_id] = messages

    async def invalidate(self, chat_id: int) -> None:
        self._messages.pop(chat_id, None)


_memory_conversation_cache = InMemoryConversationCache()


async def get_cached_conversation_messages(chat_id: int) -> list[dict] | None:
    redis_client = get_redis()
    if redis_client is None:
        return await _memory_conversation_cache.get_messages(chat_id)

    raw = await redis_client.get(_conversation_cache_key(chat_id))
    if raw is None:
        return None
    return json.loads(raw)
    
async def set_cached_conversation_messages(chat_id: int, messages: list[dict]) -> None:
    redis_client = get_redis()
    payload = json.dumps([_conversation_to_dict(msg) for msg in messages])
    if redis_client is None:
        await _memory_conversation_cache.set_messages(chat_id, json.loads(payload))
        return

    await redis_client.set(
        _conversation_cache_key(chat_id),
        payload,
        ex=settings.chat_conversation_cache_ttl_seconds,
    )


async def invalidate_conversation_cache(chat_id: int) -> None:
    redis_client = get_redis()
    if redis_client is None:
        await _memory_conversation_cache.invalidate(chat_id)
        return
    await redis_client.delete(_conversation_cache_key(chat_id))


async def update_cached_conversation_messages(
    chat_id: int, 
    update_callback: callable
) -> list[dict] | None:
    """
    Fetches the existing cached messages for a chat_id, applies a modification 
    via a callback function, saves the updated list back to cache, and returns it.
    """
    # 1. Fetch current cached data
    messages = await get_cached_conversation_messages(chat_id)
    if messages is None:
        return None  # Nothing in cache to update

    # 2. Modify the data using your custom callback logic
    updated_messages = update_callback(messages)

    # 3. Save the modified list back to Redis/Memory using your existing setter
    await set_cached_conversation_messages(chat_id, updated_messages)
    
    return updated_messages


async def append_messages_to_cache(chat_id: int, new_messages: list[dict]) -> list[dict] | None:
    def add_logic(existing_messages: list[dict]) -> list[dict]:
        # .extend() adds all elements from the new list into the existing list
        existing_messages.extend(new_messages)
        return existing_messages

    return await update_cached_conversation_messages(chat_id, add_logic)

