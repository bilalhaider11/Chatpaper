"""Tests for the chat endpoint (POST /chat/{id}/ask)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.chat import router as chat_router
from core.auth import get_current_user
from core.dependencies import get_db
from models.conversation import Conversation, ConversationList
from services.retrieval import RetrievedContext



def _make_user(user_id: int = 1):
    u = MagicMock()
    u.id = user_id
    return u


def _make_context(**kw):
    defaults = dict(
        parent_id="pid1",
        content="Relevant document content.",
        file_id=1,
        filename="report.pdf",
        page_start=1,
        page_end=3,
        element_types=["NarrativeText"],
        score=0.9,
    )
    defaults.update(kw)
    return RetrievedContext(**defaults)


def _make_db(convo_found: bool = True, history: list | None = None):
    """Return a db mock whose query() dispatch matches ConversationList vs Conversation."""
    db = MagicMock()
    history = history or []

    def _query(model):
        q = MagicMock()
        if model is ConversationList:
            convo = MagicMock() if convo_found else None
            q.filter.return_value.first.return_value = convo
        elif model is Conversation:
            q.filter.return_value.order_by.return_value.limit.return_value.all.return_value = history
        return q

    db.query.side_effect = _query
    return db


@pytest.fixture
def user():
    return _make_user(user_id=1)


@pytest.fixture
def app(user):
    a = FastAPI()
    a.include_router(chat_router)
    return a


@pytest.fixture
def client(app, user):
    db = _make_db()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        c._db = db  # expose for assertions
        yield c
    app.dependency_overrides.clear()


def _patch_llm(mocker, answer: str = "The answer is 42."):
    llm_cls = mocker.patch("api.routers.chat.ChatOpenAI")
    llm_cls.return_value.invoke.return_value.content = answer
    mocker.patch("api.routers.chat.SystemMessage", side_effect=lambda content: content)
    mocker.patch("api.routers.chat.HumanMessage", side_effect=lambda content: content)
    mocker.patch("api.routers.chat.AIMessage", side_effect=lambda content: content)
    return llm_cls.return_value



class TestAskOwnership:
    def test_valid_own_conversation_returns_200(self, mocker, app, user):
        db = _make_db(convo_found=True)
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        mocker.patch("api.routers.chat.retrieve", return_value=[_make_context()])
        _patch_llm(mocker)
        with TestClient(app) as c:
            resp = c.post("/chat/1/ask", json={"question": "What is it?"})
        assert resp.status_code == 200

    def test_conversation_not_found_returns_404(self, mocker, app, user):
        db = _make_db(convo_found=False)
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        mocker.patch("api.routers.chat.retrieve", return_value=[])
        with TestClient(app) as c:
            resp = c.post("/chat/999/ask", json={"question": "What is it?"})
        assert resp.status_code == 404

    def test_llm_unavailable_returns_503(self, mocker, app, user):
        db = _make_db()
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        # simulates ImportError at module load time — ChatOpenAI was set to None
        with patch("api.routers.chat.ChatOpenAI", None):
            with TestClient(app) as c:
                resp = c.post("/chat/1/ask", json={"question": "q"})
        assert resp.status_code == 503


class TestAskResponse:
    def test_response_contains_answer(self, mocker, app, user):
        db = _make_db()
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        mocker.patch("api.routers.chat.retrieve", return_value=[_make_context()])
        _patch_llm(mocker, answer="Because of X.")
        with TestClient(app) as c:
            resp = c.post("/chat/1/ask", json={"question": "Why?"})
        assert resp.json()["answer"] == "Because of X."

    def test_response_contains_conversation_id(self, mocker, app, user):
        db = _make_db()
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        mocker.patch("api.routers.chat.retrieve", return_value=[])
        _patch_llm(mocker)
        with TestClient(app) as c:
            resp = c.post("/chat/7/ask", json={"question": "q"})
        assert resp.json()["conversation_id"] == 7

    def test_citations_populated_from_contexts(self, mocker, app, user):
        db = _make_db()
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        ctx = _make_context(file_id=42, filename="paper.pdf", page_start=5, page_end=7)
        mocker.patch("api.routers.chat.retrieve", return_value=[ctx])
        _patch_llm(mocker)
        with TestClient(app) as c:
            resp = c.post("/chat/1/ask", json={"question": "q"})
        citations = resp.json()["citations"]
        assert len(citations) == 1
        assert citations[0]["file_id"] == 42
        assert citations[0]["filename"] == "paper.pdf"

    def test_no_contexts_yields_empty_citations(self, mocker, app, user):
        db = _make_db()
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        mocker.patch("api.routers.chat.retrieve", return_value=[])
        _patch_llm(mocker)
        with TestClient(app) as c:
            resp = c.post("/chat/1/ask", json={"question": "q"})
        assert resp.json()["citations"] == []


class TestAskRetrievePassthrough:
    def test_file_ids_forwarded_to_retrieve(self, mocker, app, user):
        db = _make_db()
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        retrieve_mock = mocker.patch("api.routers.chat.retrieve", return_value=[])
        _patch_llm(mocker)
        with TestClient(app) as c:
            c.post("/chat/1/ask", json={"question": "q", "file_ids": [3, 5]})
        assert retrieve_mock.call_args.kwargs["file_ids"] == [3, 5]

    def test_top_k_forwarded_to_retrieve(self, mocker, app, user):
        db = _make_db()
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        retrieve_mock = mocker.patch("api.routers.chat.retrieve", return_value=[])
        _patch_llm(mocker)
        with TestClient(app) as c:
            c.post("/chat/1/ask", json={"question": "q", "top_k": 3})
        assert retrieve_mock.call_args.kwargs["top_k"] == 3


class TestAskHistoryInjection:
    def test_conversation_rows_saved_after_ask(self, mocker, app, user):
        db = _make_db(history=[])
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        mocker.patch("api.routers.chat.retrieve", return_value=[])
        _patch_llm(mocker, answer="my answer")
        with TestClient(app) as c:
            c.post("/chat/1/ask", json={"question": "What?"})
        added = [c.args[0] for c in db.add.call_args_list]
        convos = [o for o in added if isinstance(o, Conversation)]
        assert len(convos) == 2
        user_turns = [c for c in convos if c.user_type == "user"]
        asst_turns = [c for c in convos if c.user_type == "assistant"]
        assert len(user_turns) == 1
        assert len(asst_turns) == 1

    def test_assistant_row_contains_llm_answer(self, mocker, app, user):
        db = _make_db(history=[])
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        mocker.patch("api.routers.chat.retrieve", return_value=[])
        _patch_llm(mocker, answer="definitive answer")
        with TestClient(app) as c:
            c.post("/chat/1/ask", json={"question": "q"})
        added = [c.args[0] for c in db.add.call_args_list]
        asst = [o for o in added if isinstance(o, Conversation) and o.user_type == "assistant"]
        assert asst[0].statement == "definitive answer"

    def test_history_turns_included_in_llm_call(self, mocker, app, user):
        past_user = MagicMock(spec=Conversation)
        past_user.user_type = "user"
        past_user.statement = "previous question"
        past_asst = MagicMock(spec=Conversation)
        past_asst.user_type = "assistant"
        past_asst.statement = "previous answer"

        db = _make_db(history=[past_asst, past_user])  # desc order; will be reversed
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        mocker.patch("api.routers.chat.retrieve", return_value=[])
        llm = _patch_llm(mocker)
        with TestClient(app) as c:
            c.post("/chat/1/ask", json={"question": "new question"})
        # messages = [system, ...history..., human(new question)]
        messages = llm.invoke.call_args[0][0]
        assert len(messages) >= 4  # system + 2 history + current question
