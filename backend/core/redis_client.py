#from typing import Optional
#
#import redis as redis_lib
#
#from core.config import settings
#
#_redis_client: Optional[redis_lib.Redis] = None
#
#
#def get_redis_client() -> redis_lib.Redis:
#    # redis.from_url is lazy — no actual TCP connect until first command
#    global _redis_client
#    if _redis_client is None:
#        _redis_client = redis_lib.Redis.from_url(
#            settings.redis_url,
#            decode_responses=True,
#        )
#    return _redis_client
#
#
#def reset_redis_client() -> None:  # test helper only
#    global _redis_client
#    _redis_client = None



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
