import logging
import redis.asyncio as redis
from core.config import settings
logger = logging.getLogger(__name__)

_redis: redis.Redis | None = None


def get_redis() -> redis.Redis | None:
    return _redis


async def start_redis() -> None:
    global _redis
    try:
        client = redis.from_url(settings.redis_url, decode_responses=True)
        await client.ping()
        _redis = client
        logger.info("Redis connected at %s", settings.redis_url)
    except Exception:
        logger.warning(
            "Redis unavailable (%s); chat cache will use in-memory fallback",
            settings.redis_url,
        )
        _redis = None


async def stop_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
