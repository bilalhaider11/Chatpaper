"""
Phase 0 — test_redis_client.py

Verifies that core/redis_client.py:
  - Creates a Redis client from the URL in settings
  - Returns the same instance on repeated calls (singleton)
  - Creates the client with decode_responses=True
  - reset_redis_client() clears the singleton
  - Does NOT raise on creation when Redis is unreachable (lazy connection)
  - Raises an error only when a command is issued against an unavailable server
"""

from unittest.mock import MagicMock, patch

import pytest

from core.redis_client import get_redis_client, reset_redis_client
from core.config import settings


@pytest.fixture(autouse=True)
def clear_singleton():
    """Ensure every test starts with a fresh (None) singleton."""
    reset_redis_client()
    yield
    reset_redis_client()


# ── Client creation ───────────────────────────────────────────────────────────

class TestGetRedisClient:
    def test_creates_client_from_url(self):
        with patch("core.redis_client.redis_lib.Redis.from_url") as mock_from_url:
            mock_from_url.return_value = MagicMock()
            get_redis_client()
            mock_from_url.assert_called_once()

    def test_uses_redis_url_from_settings(self):
        with patch("core.redis_client.redis_lib.Redis.from_url") as mock_from_url:
            mock_from_url.return_value = MagicMock()
            get_redis_client()
            args, _ = mock_from_url.call_args
            assert args[0] == settings.redis_url

    def test_decode_responses_is_true(self):
        with patch("core.redis_client.redis_lib.Redis.from_url") as mock_from_url:
            mock_from_url.return_value = MagicMock()
            get_redis_client()
            _, kwargs = mock_from_url.call_args
            assert kwargs.get("decode_responses") is True

    def test_returns_redis_instance(self):
        mock_redis = MagicMock()
        with patch("core.redis_client.redis_lib.Redis.from_url", return_value=mock_redis):
            client = get_redis_client()
            assert client is mock_redis


# ── Singleton behaviour ───────────────────────────────────────────────────────

class TestRedisClientSingleton:
    def test_same_instance_returned_on_repeated_calls(self):
        mock_redis = MagicMock()
        with patch("core.redis_client.redis_lib.Redis.from_url", return_value=mock_redis):
            c1 = get_redis_client()
            c2 = get_redis_client()
            assert c1 is c2

    def test_from_url_called_only_once_on_multiple_gets(self):
        with patch("core.redis_client.redis_lib.Redis.from_url") as mock_from_url:
            mock_from_url.return_value = MagicMock()
            for _ in range(5):
                get_redis_client()
            assert mock_from_url.call_count == 1


# ── Singleton reset ───────────────────────────────────────────────────────────

class TestResetRedisClient:
    def test_reset_clears_singleton(self):
        with patch("core.redis_client.redis_lib.Redis.from_url") as mock_from_url:
            mock_from_url.return_value = MagicMock()
            get_redis_client()
            reset_redis_client()
            get_redis_client()
            assert mock_from_url.call_count == 2

    def test_reset_on_uninitialised_singleton_does_not_raise(self):
        reset_redis_client()
        reset_redis_client()

    def test_after_reset_new_instance_is_created(self):
        with patch("core.redis_client.redis_lib.Redis.from_url") as mock_from_url:
            instance_a = MagicMock(name="a")
            instance_b = MagicMock(name="b")
            mock_from_url.side_effect = [instance_a, instance_b]

            c1 = get_redis_client()
            reset_redis_client()
            c2 = get_redis_client()

            assert c1 is instance_a
            assert c2 is instance_b
            assert c1 is not c2


# ── Lazy connection (no eager connect at creation) ────────────────────────────

class TestRedisLazyConnection:
    def test_client_creation_does_not_raise_when_redis_unreachable(self):
        """
        Redis.from_url() itself is lazy — it does not connect until a command
        is issued. Verify that get_redis_client() never forces an eager ping.
        """
        with patch("core.redis_client.redis_lib.Redis.from_url") as mock_from_url:
            mock_redis = MagicMock()
            mock_from_url.return_value = mock_redis
            client = get_redis_client()
            mock_redis.ping.assert_not_called()

    def test_connection_error_raised_only_on_command(self):
        """
        If the server is unreachable, the error surfaces on the first command
        (e.g. ping), not during client construction.
        """
        import redis as redis_lib
        mock_redis = MagicMock()
        mock_redis.ping.side_effect = redis_lib.exceptions.ConnectionError("unreachable")

        with patch("core.redis_client.redis_lib.Redis.from_url", return_value=mock_redis):
            client = get_redis_client()
            with pytest.raises(redis_lib.exceptions.ConnectionError, match="unreachable"):
                client.ping()
