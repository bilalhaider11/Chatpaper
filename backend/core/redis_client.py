from typing import Optional

import redis as redis_lib

from core.config import settings

_redis_client: Optional[redis_lib.Redis] = None


def get_redis_client() -> redis_lib.Redis:
    # redis.from_url is lazy — no actual TCP connect until first command
    global _redis_client
    if _redis_client is None:
        _redis_client = redis_lib.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    return _redis_client


def reset_redis_client() -> None:  # test helper only
    global _redis_client
    _redis_client = None
