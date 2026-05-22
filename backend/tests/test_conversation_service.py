from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from models.conversation import Conversation
from schema.conversation import ConversationListBase, ConversationResponse


def _make_user(user_id: int = 1) -> MagicMock:
    u = MagicMock()
    u.id = user_id
    return u


class TestCreateConversationList:
    def test_creates_with_correct_user_id(self):
        from services.conversation import create_conversation_list
        db = MagicMock()
        create_conversation_list(_make_user(user_id=3), db)
        added = db.add.call_args[0][0]
        assert added.user_id == 3
        assert added.is_active is True


class TestUpdateConversationTitle:
    def test_updates_title_successfully(self):
        from services.conversation import update_conversation_title
        db = MagicMock()
        result = update_conversation_title(
            ConversationListBase(conversation_title="New Title"), 1, db
        )
        db.execute.assert_called_once()
        assert result == {"Title": "Updated Successfully"}

    def test_empty_title_raises_400(self):
        from services.conversation import update_conversation_title
        db = MagicMock()
        with pytest.raises(HTTPException) as exc:
            update_conversation_title(ConversationListBase(conversation_title=None), 1, db)
        assert exc.value.status_code == 400


class TestAddConversation:
    def test_adds_conversation_row(self):
        from services.conversation import add_conversation
        db = MagicMock()
        add_conversation(ConversationResponse(statement="Hello", user_type="user"), chat_id=5, db=db)
        added = db.add.call_args[0][0]
        assert added.chat_id == 5
        assert added.statement == "Hello"

    def test_zero_chat_id_raises_400(self):
        from services.conversation import add_conversation
        db = MagicMock()
        with pytest.raises(HTTPException) as exc:
            add_conversation(
                ConversationResponse(statement="Hi", user_type="user"), chat_id=0, db=db
            )
        assert exc.value.status_code == 400


class TestGetConversations:
    def test_returns_conversations(self):
        from services.conversation import get_conversations
        db = MagicMock()
        rows = [MagicMock(spec=Conversation)]
        db.query.return_value.order_by.return_value.where.return_value.all.return_value = rows
        assert get_conversations(chat_list_id=1, db=db) == rows

    def test_zero_chat_list_id_raises_400(self):
        from services.conversation import get_conversations
        db = MagicMock()
        with pytest.raises(HTTPException) as exc:
            get_conversations(chat_list_id=0, db=db)
        assert exc.value.status_code == 400
