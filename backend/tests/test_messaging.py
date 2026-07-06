"""Tests for conversation message queue (Redis -> bulk DB insert)."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from services.chat_cache import QueuedChatMessage, _message_from_json, _message_to_json
from services.messaging import bulk_insert_messages, handle_conversation_message


class TestQueuedMessageSerialization:
    def test_datetime_roundtrip(self):
        ts = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        msg = QueuedChatMessage(
            chat_id=42,
            user_type="user",
            statement="hello",
            created_at=ts,
            temp_id="abc",
        )
        restored = _message_from_json(_message_to_json(msg))
        assert restored.chat_id == 42
        assert restored.user_type == "user"
        assert restored.statement == "hello"
        assert restored.temp_id == "abc"
        assert restored.created_at == ts


class TestBulkInsertMessages:
    def test_inserts_rows(self):
        db = MagicMock()
        rows = [
            QueuedChatMessage(
                chat_id=1,
                user_type="user",
                statement="q",
                created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
            ),
            QueuedChatMessage(
                chat_id=1,
                user_type="assistant",
                statement="a",
                created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
            ),
        ]
        mock_conv = MagicMock()
        mock_conv.id = 99

        def refresh_side_effect(obj):
            obj.id = 99

        db.refresh.side_effect = refresh_side_effect

        with patch("services.messaging.Conversation", return_value=mock_conv):
            result = bulk_insert_messages(db, rows)

        db.add_all.assert_called_once()
        db.commit.assert_called_once()
        assert len(result) == 2


@pytest.mark.asyncio
async def test_handle_conversation_message_enqueues_and_caches():
    with (
        patch("services.messaging.publish_chat_message") as mock_publish,
        patch("services.messaging.append_messages_to_cache") as mock_cache,
    ):
        await handle_conversation_message(
            chat_id=7,
            user_type="user",
            statement="test question",
        )
        mock_publish.assert_awaited_once()
        mock_cache.assert_awaited_once()
        args, _ = mock_cache.call_args
        assert args[0] == 7
        assert args[1][0]["statement"] == "test question"
