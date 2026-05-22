import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from aio_pika import DeliveryMode
import aio_pika
from aio_pika.abc import AbstractIncomingMessage
from sqlalchemy.orm import Session

from core.config import settings
from core.database import SessionLocal
from models.conversation import Conversation
from services.chat_cache import (
    QueuedChatMessage,
    drain_flush_queue,
    enqueue_message,
    flush_queue_size,
)

logger = logging.getLogger(__name__)

QUEUE_NAME = "chat_messages"
USER_TYPE_USER = "user"
USER_TYPE_SYSTEM = "system"
ALLOWED_USER_TYPES = {USER_TYPE_USER, USER_TYPE_SYSTEM}


@dataclass
class QueuedChatMessage:
    chat_id: int
    user_type: str
    statement: str
    temp_id: str | None = None
    enqueued_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ChatMessageBuffer:
    def __init__(self) -> None:
        self._items: list[QueuedChatMessage] = []
        self._lock = asyncio.Lock()

    async def add(self, item: QueuedChatMessage) -> None:
        async with self._lock:
            self._items.append(item)

    async def drain(self) -> list[QueuedChatMessage]:
        async with self._lock:
            batch = self._items[:]
            self._items.clear()
            return batch

    async def size(self) -> int:
        async with self._lock:
            return len(self._items)


_buffer = ChatMessageBuffer()
_connection: aio_pika.RobustConnection | None = None
_channel: aio_pika.RobustChannel | None = None
_consumer_task: asyncio.Task | None = None
_flush_task: asyncio.Task | None = None

def bulk_insert_messages(db: Session, messages: list[QueuedChatMessage]) -> list[Conversation]:
    rows = [
        Conversation(
            chat_id=msg.chat_id,
            user_type=msg.user_type,
            statement=msg.statement,
        )
        
        for msg in messages
    ]
    
    db.add_all(rows)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


async def flush_buffer_to_db() -> int:
    batch = await drain_flush_queue()

    if not batch:
        return 0

    def _persist() -> int:
        db = SessionLocal()
        try:
            bulk_insert_messages(db, batch)
            return len(batch)
        finally:
            db.close()

    count = await asyncio.to_thread(_persist)
    logger.info("Flushed %s chat messages to database", count)
    return count


async def _periodic_flush() -> None:
    while True:
        await asyncio.sleep(settings.chat_flush_interval_seconds)
        try:
            if await flush_queue_size() > 0:
                await flush_buffer_to_db()
        except Exception:
            logger.exception("Periodic chat flush failed")


async def _on_queue_message(message: AbstractIncomingMessage) -> None:
    async with message.process():
        payload = json.loads(message.body.decode())
        queued = QueuedChatMessage(
            chat_id=int(payload["chat_id"]),
            user_type=payload["user_type"],
            statement=payload["statement"],
            temp_id=payload.get("temp_id"),
        )
        if queued.user_type not in ALLOWED_USER_TYPES:
            return
        await _buffer.add(queued)
        

async def publish_chat_message(
    chat_id: int,
    user_type: str,
    statement: str,
    temp_id: str | None = None,
) -> None:
    if user_type not in ALLOWED_USER_TYPES:
        raise ValueError(f"user_type must be one of {ALLOWED_USER_TYPES}")

    queued = QueuedChatMessage(
        chat_id=chat_id,
        user_type=user_type,
        statement=statement,
        temp_id=temp_id,
    )

    await enqueue_message(queued)

    if _channel is None:
        return

    payload = {
        "chat_id": chat_id,
        "user_type": user_type,
        "statement": statement,
        "temp_id": temp_id,
    }
    await _channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps(payload).encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
        ),
        routing_key=QUEUE_NAME,
    )


async def start_messaging() -> None:
    global _connection, _channel, _consumer_task, _flush_task

    if _flush_task is None:
        _flush_task = asyncio.create_task(_periodic_flush())

    try:
        _connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        _channel = await _connection.channel()
        await _channel.set_qos(prefetch_count=1)
        queue = await _channel.declare_queue(QUEUE_NAME, durable=True)
        _consumer_task = asyncio.create_task(queue.consume(_on_queue_message))
        logger.info("RabbitMQ chat consumer started on queue %s", QUEUE_NAME)
    except Exception:
        logger.warning(
            "RabbitMQ unavailable (%s); using in-memory buffer only",
            settings.rabbitmq_url,
        )
        _connection = None
        _channel = None


async def stop_messaging() -> None:
    global _connection, _channel, _consumer_task, _flush_task

    if _consumer_task:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
        _consumer_task = None

    if _flush_task:
        _flush_task.cancel()
        try:
            await _flush_task
        except asyncio.CancelledError:
            pass
        _flush_task = None

    try:
        await flush_buffer_to_db()
        
    except Exception:
        logger.exception("Final chat flush failed")

    if _channel:
        await _channel.close()
        _channel = None
    if _connection:
        await _connection.close()
        _connection = None



