import asyncio
import logging

from sqlalchemy import update,case

from core.config import settings
from core.database import SessionLocal
from core.redis_client import get_redis
from models.auth import User
from services.credits import CREDITS_DIRTY_SET, CREDITS_KEY_PREFIX

logger = logging.getLogger(__name__)

_flush_task: asyncio.Task | None = None


async def flush_credits_to_db() -> int:
    redis = get_redis()
    if redis is None:
        return 0

    dirty_ids = await redis.smembers(CREDITS_DIRTY_SET)
    if not dirty_ids:
        return 0

    updates: list[tuple[int, int]] = []
    for user_id_str in dirty_ids:
        user_id = int(user_id_str)
        cached = await redis.get(f"{CREDITS_KEY_PREFIX}{user_id}")
        if cached is None:
            await redis.srem(CREDITS_DIRTY_SET, user_id_str)
            continue
        updates.append((user_id, int(cached)))

    if not updates:
        return 0

    
    def _persist(batch: list[tuple[int, int]]) -> int:
        if not batch:
            return 0
    
        db = SessionLocal()
    
        try:
            mapping = {user_id: credits for user_id, credits in batch}
    
            stmt = (
                update(User)
                .where(User.id.in_(mapping.keys()))
                .values(
                    credits=case(
                        mapping,
                        value=User.id,
                    )
                )
            )
    
            db.execute(stmt)
            db.commit()
    
            return len(batch)
    
        except Exception:
            db.rollback()
            raise
    
        finally:
            db.close()

    count = await asyncio.to_thread(_persist, updates)
    for user_id, _ in updates:
        await redis.srem(CREDITS_DIRTY_SET, str(user_id))

    logger.info("Flushed credits for %s user(s) to database", count)
    return count


async def _periodic_credits_flush() -> None:
    while True:
        await asyncio.sleep(settings.credits_flush_interval_seconds)
        try:
            await flush_credits_to_db()
        except Exception:
            logger.exception("Periodic credits flush failed")


async def start_credits_sync() -> None:
    global _flush_task
    if _flush_task is None:
        _flush_task = asyncio.create_task(_periodic_credits_flush())
        logger.info(
            "Credits sync started (interval=%ss)",
            settings.credits_flush_interval_seconds,
        )


async def stop_credits_sync() -> None:
    global _flush_task

    if _flush_task:
        _flush_task.cancel()
        try:
            await _flush_task
        except asyncio.CancelledError:
            pass
        _flush_task = None

    try:
        await flush_credits_to_db()
    except Exception:
        logger.exception("Final credits flush failed")
