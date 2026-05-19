from typing import Optional

import redis as redis_lib

from core.config import settings

_redis_client: Optional[redis_lib.Redis] = None


def get_redis_client() -> redis_lib.Redis:
    """Return the shared Redis client, creating it on first call.

    The client does not connect until the first command is issued,
    so this function is safe to call even if Redis is temporarily unavailable.
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = redis_lib.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    return _redis_client


def reset_redis_client() -> None:
    """Clear the singleton — intended for use in tests only."""
    global _redis_client
    _redis_client = None
