from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from models.conversation import Conversation


def _make_user(user_id: int = 1) -> MagicMock:
    u = MagicMock()
    u.id = user_id
    return u


class TestCreateConversationList:
    @pytest.mark.asyncio
    async def test_creates_with_correct_user_id_and_file(self, mocker):
        from services.conversation import create_conversation_list

        file_record = MagicMock()
        file_record.id = 10
        file_record.filename = "paper.pdf"
        mocker.patch(
            "services.conversation._get_owned_file_for_user",
            new_callable=AsyncMock,
            return_value=file_record,
        )

        db = AsyncMock()
        await create_conversation_list(_make_user(user_id=3), db, file_id=10)
        added = db.add.call_args[0][0]
        assert added.user_id == 3
        assert added.file_id == 10
        assert added.conversation_title == "paper.pdf"
        assert added.is_active is True
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_missing_file_raises_400(self, mocker):
        from services.conversation import create_conversation_list

        mocker.patch(
            "services.conversation._get_owned_file_for_user",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=400, detail="file required"),
        )
        db = AsyncMock()
        with pytest.raises(HTTPException) as exc:
            await create_conversation_list(_make_user(), db, file_id=99)
        assert exc.value.status_code == 400


class TestUpdateConversationTitle:
    @pytest.mark.asyncio
    async def test_updates_title_successfully(self):
        from services.conversation import update_conversation_title

        db = AsyncMock()
        result = await update_conversation_title("New Title", 1, 1, db)
        db.execute.assert_awaited_once()
        assert result == {"Title": "Updated Successfully"}

    @pytest.mark.asyncio
    async def test_empty_title_raises_400(self):
        from services.conversation import update_conversation_title

        db = AsyncMock()
        with pytest.raises(HTTPException) as exc:
            await update_conversation_title("   ", 1, 1, db)
        assert exc.value.status_code == 400


class TestGetConversations:
    @pytest.mark.asyncio
    async def test_zero_chat_list_id_raises_400(self):
        from services.conversation import get_conversations

        db = AsyncMock()
        with pytest.raises(HTTPException) as exc:
            await get_conversations(chat_list_id=0, db=db)
        assert exc.value.status_code == 400
