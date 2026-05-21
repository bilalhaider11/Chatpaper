from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from models.auth import User
from schema.auth import UserCreate, UserUpdate


def _make_user(user_id: int = 1, email: str = "user@example.com") -> MagicMock:
    u = MagicMock(spec=User)
    u.id = user_id
    u.email = email
    u.password = "hashed"
    u.role = "user"
    return u


def _make_db(user: User | None = None) -> MagicMock:
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user
    db.query.return_value.offset.return_value.limit.return_value.all.return_value = (
        [user] if user else []
    )
    return db


class TestGetUserByEmail:
    def test_returns_user_when_found(self):
        from services.auth import get_user_by_email
        user = _make_user()
        db = _make_db(user=user)
        assert get_user_by_email(db, "user@example.com") is user

    def test_returns_none_when_not_found(self):
        from services.auth import get_user_by_email
        db = _make_db(user=None)
        assert get_user_by_email(db, "missing@example.com") is None


class TestGetUserById:
    def test_returns_user_when_found(self):
        from services.auth import get_user_by_id
        user = _make_user()
        db = _make_db(user=user)
        assert get_user_by_id(db, 1) is user

    def test_raises_404_when_not_found(self):
        from services.auth import get_user_by_id
        db = _make_db(user=None)
        with pytest.raises(HTTPException) as exc:
            get_user_by_id(db, 999)
        assert exc.value.status_code == 404


class TestCreateNewUser:
    def test_adds_user_with_hashed_password(self):
        from services.auth import create_new_user
        db = MagicMock()
        user_in = UserCreate(email="new@example.com", password="plaintext")
        create_new_user(db, user_in)
        added = db.add.call_args[0][0]
        assert added.email == "new@example.com"
        assert added.password != "plaintext"
        db.commit.assert_called_once()


class TestUpdateUser:
    def test_partial_update_sets_only_provided_fields(self):
        from services.auth import update_user
        user = _make_user()
        db = _make_db(user=user)
        update_user(db, 1, UserUpdate(is_active=False))
        assert user.is_active is False

    def test_password_field_is_hashed(self):
        from services.auth import update_user
        user = _make_user()
        db = _make_db(user=user)
        update_user(db, 1, UserUpdate(password="newpass"))
        assert user.password != "newpass"


class TestDeleteUser:
    def test_returns_user_data_dict(self):
        from services.auth import delete_user
        user = _make_user(user_id=5, email="del@example.com")
        db = _make_db(user=user)
        result = delete_user(db, 5)
        assert result["id"] == 5
        assert result["email"] == "del@example.com"
        db.delete.assert_called_once_with(user)

    def test_raises_404_for_missing_user(self):
        from services.auth import delete_user
        db = _make_db(user=None)
        with pytest.raises(HTTPException) as exc:
            delete_user(db, 999)
        assert exc.value.status_code == 404
