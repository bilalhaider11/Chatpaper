from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.auth.auth import router as auth_router
from core.auth import get_current_user
from core.dependencies import get_db
from models.auth import UserRole


def _make_user(user_id: int = 1, email: str = "user@example.com", role: UserRole = UserRole.user):
    u = MagicMock()
    u.id = user_id
    u.email = email
    u.role = role
    return u


@pytest.fixture
def app():
    a = FastAPI()
    a.include_router(auth_router)
    a.dependency_overrides[get_db] = lambda: MagicMock()
    yield a
    a.dependency_overrides.clear()


class TestLogin:
    def test_valid_credentials_return_token(self, mocker, app):
        user = _make_user()
        mocker.patch("core.auth.authenticate_user", return_value=user)
        mocker.patch("core.auth.create_access_token", return_value="tok123")
        with TestClient(app) as c:
            resp = c.post("/auth/login", data={"username": "user@example.com", "password": "pass"})
        assert resp.status_code == 200
        assert resp.json()["access_token"] == "tok123"

    def test_wrong_password_returns_401(self, mocker, app):
        mocker.patch("core.auth.authenticate_user", return_value=False)
        with TestClient(app) as c:
            resp = c.post("/auth/login", data={"username": "x@x.com", "password": "wrong"})
        assert resp.status_code == 401


class TestCreateUser:
    def test_duplicate_email_returns_400(self, mocker, app):
        mocker.patch("services.auth.get_user_by_email", return_value=_make_user())
        with TestClient(app) as c:
            resp = c.post("/auth/users", json={"email": "dup@example.com", "password": "pass"})
        assert resp.status_code == 400

    def test_new_user_created_successfully(self, mocker, app):
        mocker.patch("services.auth.get_user_by_email", return_value=None)
        mocker.patch("services.auth.create_new_user", return_value=_make_user())
        with TestClient(app) as c:
            resp = c.post("/auth/users", json={"email": "new@example.com", "password": "pass"})
        assert resp.status_code == 200


class TestReadMe:
    def test_returns_current_user(self, app):
        user = _make_user()
        app.dependency_overrides[get_current_user] = lambda: user
        with TestClient(app) as c:
            resp = c.get("/auth/users/me")
        assert resp.status_code == 200
