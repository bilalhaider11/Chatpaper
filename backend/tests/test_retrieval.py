from __future__ import annotations

from unittest.mock import MagicMock

import pytest



class TestWhere:
    def test_no_file_ids_returns_user_filter(self):
        from services.retrieval import _where
        assert _where(7, None) == {"user_id": 7}

    def test_empty_list_returns_user_filter(self):
        from services.retrieval import _where
        assert _where(7, []) == {"user_id": 7}

    def test_single_file_id_uses_and_filter(self):
        from services.retrieval import _where
        assert _where(7, [42]) == {"$and": [{"user_id": 7}, {"file_id": 42}]}

    def test_multiple_file_ids_uses_in_filter(self):
        from services.retrieval import _where
        result = _where(7, [1, 2, 3])
        assert result == {"$and": [{"user_id": 7}, {"file_id": {"$in": [1, 2, 3]}}]}



class TestChromaQuery:
    def test_returns_collection_query_result(self):
        from services.retrieval import _chroma_query
        col = MagicMock()
        col.query.return_value = {"metadatas": [["m1"]], "distances": [[0.1]]}
        result = _chroma_query(col, [0.1, 0.2], {"user_id": 1}, 5)
        assert result["metadatas"] == [["m1"]]

    def test_exception_returns_empty_result(self):
        from services.retrieval import _chroma_query
        col = MagicMock()
        col.query.side_effect = Exception("chroma unavailable")
        result = _chroma_query(col, [0.1], {"user_id": 1}, 5)
        assert result == {"metadatas": [[]], "distances": [[]]}



class TestDenseRetrieve:
    def _mock_col(self, mocker, metas, dists):
        col = MagicMock()
        col.query.return_value = {"metadatas": [metas], "distances": [dists]}
        mocker.patch("services.retrieval.get_child_chunks_collection", return_value=col)

    def test_sim_is_one_minus_distance(self, mocker):
        from services.retrieval import _dense_retrieve
        self._mock_col(mocker, [{"parent_id": "p1"}], [0.3])
        result = _dense_retrieve([0.1], 1, None, 5)
        assert abs(result["p1"] - 0.7) < 1e-9

    def test_keeps_best_sim_per_parent(self, mocker):
        from services.retrieval import _dense_retrieve
        # same parent_id appears twice; distances 0.2 and 0.5 → sims 0.8 and 0.5 → keep 0.8
        self._mock_col(mocker,
            [{"parent_id": "p1"}, {"parent_id": "p1"}],
            [0.2, 0.5],
        )
        result = _dense_retrieve([0.1], 1, None, 5)
        assert abs(result["p1"] - 0.8) < 1e-9

    def test_missing_parent_id_skipped(self, mocker):
        from services.retrieval import _dense_retrieve
        self._mock_col(mocker, [{}], [0.1])
        assert _dense_retrieve([0.1], 1, None, 5) == {}

    def test_empty_results_returns_empty(self, mocker):
        from services.retrieval import _dense_retrieve
        self._mock_col(mocker, [], [])
        assert _dense_retrieve([0.1], 1, None, 5) == {}



class TestBm25Retrieve:
    def _make_row(self, pid, rank):
        r = MagicMock()
        r.id = pid
        r.rank = rank
        return r

    def test_returns_dict_of_rank_scores(self):
        from services.retrieval import _bm25_retrieve
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = [
            self._make_row("p1", 0.8),
            self._make_row("p2", 0.4),
        ]
        result = _bm25_retrieve("text query", 1, None, db, 5)
        assert result == {"p1": 0.8, "p2": 0.4}

    def test_db_exception_returns_empty_dict(self):
        from services.retrieval import _bm25_retrieve
        db = MagicMock()
        db.execute.side_effect = Exception("db error")
        assert _bm25_retrieve("q", 1, None, db, 5) == {}

    def test_file_ids_included_in_params_when_provided(self):
        from services.retrieval import _bm25_retrieve
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = []
        _bm25_retrieve("q", 1, [5, 6], db, 5)
        params = db.execute.call_args[0][1]
        assert params.get("file_ids") == [5, 6]

    def test_file_ids_absent_from_params_when_none(self):
        from services.retrieval import _bm25_retrieve
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = []
        _bm25_retrieve("q", 1, None, db, 5)
        params = db.execute.call_args[0][1]
        assert "file_ids" not in params



class TestRrf:
    def test_score_formula_single_list(self):
        from services.retrieval import _rrf
        scores = _rrf([["p1", "p2", "p3"]], k=60)
        assert abs(scores["p1"] - 1 / 61) < 1e-12
        assert abs(scores["p2"] - 1 / 62) < 1e-12
        assert abs(scores["p3"] - 1 / 63) < 1e-12

    def test_parent_in_two_lists_scores_higher_than_one(self):
        from services.retrieval import _rrf
        # p1 in both lists, p2 only in first
        scores = _rrf([["p1", "p2"], ["p1"]], k=60)
        assert scores["p1"] > scores["p2"]

    def test_empty_input_returns_empty(self):
        from services.retrieval import _rrf
        assert _rrf([]) == {}

    def test_empty_inner_list_returns_empty(self):
        from services.retrieval import _rrf
        assert _rrf([[]]) == {}



class TestRetrieve:
    def _patch_embedder(self, mocker, embedding=None):
        mock_emb = MagicMock()
        mock_emb.embed_query.return_value = embedding or [0.1, 0.2]
        mocker.patch("services.retrieval.get_embedder", return_value=mock_emb)
        return mock_emb

    def _make_dp(self, pid: str, file_id: int = 1):
        from models.ingestion import DocumentParent
        dp = MagicMock(spec=DocumentParent)
        dp.id = pid
        dp.content = f"content for {pid}"
        dp.file_id = file_id
        dp.page_start = 1
        dp.page_end = 2
        dp.element_types = ["NarrativeText"]
        return dp

    def test_no_results_returns_empty_list(self, mocker):
        from services.retrieval import retrieve
        self._patch_embedder(mocker)
        mocker.patch("services.retrieval._dense_retrieve", return_value={})
        mocker.patch("services.retrieval._bm25_retrieve", return_value={})
        mocker.patch("services.retrieval._summary_route", return_value=None)
        result = retrieve("q", 1, MagicMock())
        assert result == []

    def test_bm25_disabled_does_not_call_bm25_retrieve(self, mocker):
        from services.retrieval import retrieve
        self._patch_embedder(mocker)
        mocker.patch("services.retrieval._dense_retrieve", return_value={})
        mocker.patch("services.retrieval._summary_route", return_value=None)
        bm25_mock = mocker.patch("services.retrieval._bm25_retrieve")
        retrieve("q", 1, MagicMock(), use_bm25=False)
        bm25_mock.assert_not_called()

    def test_summary_routing_narrows_routing_file_ids(self, mocker):
        from services.retrieval import retrieve
        self._patch_embedder(mocker)
        mocker.patch("services.retrieval._summary_route", return_value=[3, 4])
        dense_mock = mocker.patch("services.retrieval._dense_retrieve", return_value={})
        mocker.patch("services.retrieval._bm25_retrieve", return_value={})
        retrieve("q", 1, MagicMock(), file_ids=None, use_summary_routing=True)
        # routing_file_ids is the third positional arg to _dense_retrieve
        assert dense_mock.call_args[0][2] == [3, 4]

    def test_explicit_file_ids_bypass_summary_routing(self, mocker):
        from services.retrieval import retrieve
        self._patch_embedder(mocker)
        route_mock = mocker.patch("services.retrieval._summary_route")
        mocker.patch("services.retrieval._dense_retrieve", return_value={})
        mocker.patch("services.retrieval._bm25_retrieve", return_value={})
        retrieve("q", 1, MagicMock(), file_ids=[1, 2], use_summary_routing=True)
        route_mock.assert_not_called()

    def test_top_k_limits_output(self, mocker):
        from services.retrieval import retrieve
        self._patch_embedder(mocker)
        mocker.patch("services.retrieval._summary_route", return_value=None)
        mocker.patch("services.retrieval._dense_retrieve", return_value={
            "p1": 0.9, "p2": 0.8, "p3": 0.7, "p4": 0.6, "p5": 0.5,
        })
        mocker.patch("services.retrieval._bm25_retrieve", return_value={})

        rows = [(self._make_dp(f"p{i}", i), "file.pdf") for i in range(1, 6)]
        db = MagicMock()
        db.query.return_value.join.return_value.filter.return_value.all.return_value = rows

        result = retrieve("q", 1, db, top_k=2)
        assert len(result) == 2

    def test_returns_retrieved_context_objects(self, mocker):
        from services.retrieval import retrieve, RetrievedContext
        self._patch_embedder(mocker)
        mocker.patch("services.retrieval._summary_route", return_value=None)
        mocker.patch("services.retrieval._dense_retrieve", return_value={"p1": 0.9})
        mocker.patch("services.retrieval._bm25_retrieve", return_value={})

        rows = [(self._make_dp("p1", 1), "report.pdf")]
        db = MagicMock()
        db.query.return_value.join.return_value.filter.return_value.all.return_value = rows

        result = retrieve("q", 1, db, top_k=5)
        assert len(result) == 1
        assert isinstance(result[0], RetrievedContext)
        assert result[0].parent_id == "p1"
        assert result[0].filename == "report.pdf"
