from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.conversation import router as conversation_router
from core.auth import get_current_user
from core.dependencies import get_db
from models.auth import UserRole
from models.conversation import ConversationList


def _make_user(user_id: int = 1, role: UserRole = UserRole.user):
    u = MagicMock()
    u.id = user_id
    u.role = role
    return u


def _make_convo(convo_id: int = 1, user_id: int = 1) -> MagicMock:
    c = MagicMock(spec=ConversationList)
    c.id = convo_id
    c.user_id = user_id
    c.conversation_title = "test"
    c.is_active = True
    return c


def _make_db(convo: ConversationList | None = None) -> MagicMock:
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = convo
    db.query.return_value.where.return_value.all.return_value = [convo] if convo else []
    db.query.return_value.where.return_value.where.return_value.all.return_value = (
        [convo] if convo else []
    )
    return db


@pytest.fixture
def app():
    a = FastAPI()
    a.include_router(conversation_router)
    yield a
    a.dependency_overrides.clear()


class TestCreateConversationList:
    def test_returns_200(self, mocker, app):
        user = _make_user()
        mocker.patch(
            "services.conversation.create_conversation_list", return_value=_make_convo()
        )
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: MagicMock()
        with TestClient(app) as c:
            resp = c.post("/conversation/inconversationlist")
        assert resp.status_code == 200


class TestUpdateConversationTitle:
    def test_own_conversation_returns_200(self, mocker, app):
        user = _make_user(user_id=1)
        mocker.patch(
            "services.conversation.update_conversation_title",
            return_value={"Title": "Updated Successfully"},
        )
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: _make_db(convo=_make_convo(user_id=1))
        with TestClient(app) as c:
            resp = c.patch(
                "/conversation/conversation-title/1", json={"conversation_title": "New"}
            )
        assert resp.status_code == 200

    def test_other_users_conversation_returns_404(self, app):
        user = _make_user(user_id=2)
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: _make_db(convo=_make_convo(user_id=1))
        with TestClient(app) as c:
            resp = c.patch(
                "/conversation/conversation-title/1", json={"conversation_title": "New"}
            )
        assert resp.status_code == 404

    def test_missing_conversation_returns_404(self, app):
        user = _make_user()
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: _make_db(convo=None)
        with TestClient(app) as c:
            resp = c.patch(
                "/conversation/conversation-title/999", json={"conversation_title": "X"}
            )
        assert resp.status_code == 404


class TestGetConversationList:
    def test_non_admin_gets_200(self, app):
        user = _make_user(user_id=1)
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: _make_db(convo=_make_convo(user_id=1))
        with TestClient(app) as c:
            resp = c.get("/conversation/get_conversation_list")
        assert resp.status_code == 200

    def test_admin_gets_all_conversations(self, app):
        admin = _make_user(user_id=99, role=UserRole.admin)
        app.dependency_overrides[get_current_user] = lambda: admin
        app.dependency_overrides[get_db] = lambda: _make_db(convo=_make_convo(user_id=1))
        with TestClient(app) as c:
            resp = c.get("/conversation/get_conversation_list")
        assert resp.status_code == 200


class TestGetConversation:
    def test_own_conversation_returns_200(self, mocker, app):
        user = _make_user(user_id=1)
        mocker.patch("services.conversation.get_conversations", return_value=[])
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: _make_db(convo=_make_convo(user_id=1))
        with TestClient(app) as c:
            resp = c.get("/conversation/get-conversation/1")
        assert resp.status_code == 200

    def test_other_users_conversation_returns_404(self, app):
        user = _make_user(user_id=2)
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: _make_db(convo=_make_convo(user_id=1))
        with TestClient(app) as c:
            resp = c.get("/conversation/get-conversation/1")
        assert resp.status_code == 404
