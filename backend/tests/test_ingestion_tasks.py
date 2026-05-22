from __future__ import annotations

import hashlib
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from models.ingestion import IngestionJob



def _make_job(**kwargs) -> MagicMock:
    defaults = dict(id=1, status="QUEUED", current_stage=None, retry_count=0, total_stages=6)
    defaults.update(kwargs)
    job = MagicMock(spec=IngestionJob)
    for k, v in defaults.items():
        setattr(job, k, v)
    return job


def _make_file_record(filepath: str = "/files/abc_test.pdf", file_type: str = "application/pdf") -> MagicMock:
    fr = MagicMock()
    fr.id = 10
    fr.user_id = 1
    fr.filepath = filepath
    fr.file_type = file_type
    fr.total_pages = None
    fr.file_hash = None
    fr.ingestion_status = None
    return fr


def _make_parsed_element(text: str = "hello", page: int = 1, etype: str = "NarrativeText"):
    from tasks.ingestion_tasks import ParsedElement
    return ParsedElement(text=text, page_number=page, element_type=etype)


def _make_parent_chunk(text: str = "parent text", chunk_index: int = 0, etype: str = "NarrativeText"):
    from tasks.ingestion_tasks import ParentChunk
    return ParentChunk(text=text, chunk_index=chunk_index, page_start=1, page_end=1, element_types=etype)


def _make_db_mock(mocker, job, file_record, duplicate_record=None):
    # FileRecord uses a call counter — call 0 is the current file, call 1+ is the dedup re-query
    from models.file_model import FileRecord
    from models.ingestion import IngestionJob as IJ

    fr_call = {"n": 0}

    def _query(model):
        q = MagicMock()
        if model is IJ:
            q.filter.return_value.first.return_value = job
        elif model is FileRecord:
            n = fr_call["n"]
            fr_call["n"] += 1
            q.filter.return_value.first.return_value = file_record if n == 0 else duplicate_record
        else:
            q.filter.return_value.first.return_value = None
        return q

    db = MagicMock()
    db.query.side_effect = _query
    mocker.patch("tasks.ingestion_tasks.SessionLocal", return_value=db)
    return db



class TestSetStage:
    def test_sets_status_string(self):
        from tasks.ingestion_tasks import _set_stage
        job, db = _make_job(), MagicMock()
        _set_stage(job, db, 3)
        assert job.status == "STAGE_3"

    def test_sets_current_stage(self):
        from tasks.ingestion_tasks import _set_stage
        job, db = _make_job(), MagicMock()
        _set_stage(job, db, 5)
        assert job.current_stage == 5

    def test_commits(self):
        from tasks.ingestion_tasks import _set_stage
        job, db = _make_job(), MagicMock()
        _set_stage(job, db, 2)
        db.commit.assert_called_once()

    def test_stage_1_sets_started_at(self):
        from tasks.ingestion_tasks import _set_stage
        job, db = _make_job(), MagicMock()
        _set_stage(job, db, 1)
        assert job.started_at is not None

    def test_stage_2_does_not_set_started_at(self):
        from tasks.ingestion_tasks import _set_stage
        job, db = _make_job(), MagicMock()
        job.started_at = None
        _set_stage(job, db, 2)
        assert job.started_at is None



class TestComplete:
    def test_status_is_complete(self):
        from tasks.ingestion_tasks import _complete
        job, db = _make_job(), MagicMock()
        _complete(job, db, "abc")
        assert job.status == IngestionJob.STATUS_COMPLETE

    def test_sets_file_hash(self):
        from tasks.ingestion_tasks import _complete
        job, db = _make_job(), MagicMock()
        _complete(job, db, "deadbeef")
        assert job.file_hash == "deadbeef"

    def test_sets_completed_at(self):
        from tasks.ingestion_tasks import _complete
        job, db = _make_job(), MagicMock()
        _complete(job, db, "x")
        assert job.completed_at is not None

    def test_current_stage_set_to_total(self):
        from tasks.ingestion_tasks import _complete
        job = _make_job(total_stages=6)
        db = MagicMock()
        _complete(job, db, "x")
        assert job.current_stage == 6

    def test_commits(self):
        from tasks.ingestion_tasks import _complete
        job, db = _make_job(), MagicMock()
        _complete(job, db, "x")
        db.commit.assert_called_once()



class TestFailPermanent:
    def test_sets_status(self):
        from tasks.ingestion_tasks import _fail_permanent
        job, db = _make_job(), MagicMock()
        _fail_permanent(job, db, "boom", "ValueError")
        assert job.status == IngestionJob.STATUS_FAILED_PERMANENT

    def test_sets_error_message(self):
        from tasks.ingestion_tasks import _fail_permanent
        job, db = _make_job(), MagicMock()
        _fail_permanent(job, db, "disk full", "IOError")
        assert job.error_message == "disk full"

    def test_sets_error_type(self):
        from tasks.ingestion_tasks import _fail_permanent
        job, db = _make_job(), MagicMock()
        _fail_permanent(job, db, "m", "MyError")
        assert job.error_type == "MyError"

    def test_sets_completed_at(self):
        from tasks.ingestion_tasks import _fail_permanent
        job, db = _make_job(), MagicMock()
        _fail_permanent(job, db, "m", "t")
        assert job.completed_at is not None

    def test_commits(self):
        from tasks.ingestion_tasks import _fail_permanent
        job, db = _make_job(), MagicMock()
        _fail_permanent(job, db, "m", "t")
        db.commit.assert_called_once()



class TestFailRetryable:
    def test_sets_status(self):
        from tasks.ingestion_tasks import _fail_retryable
        job, db = _make_job(retry_count=0), MagicMock()
        _fail_retryable(job, db, "transient", "IOError")
        assert job.status == IngestionJob.STATUS_FAILED_RETRYABLE

    def test_increments_retry_count(self):
        from tasks.ingestion_tasks import _fail_retryable
        job, db = _make_job(retry_count=1), MagicMock()
        _fail_retryable(job, db, "m", "t")
        assert job.retry_count == 2

    def test_sets_error_message(self):
        from tasks.ingestion_tasks import _fail_retryable
        job, db = _make_job(), MagicMock()
        _fail_retryable(job, db, "network blip", "ConnectionError")
        assert job.error_message == "network blip"

    def test_commits(self):
        from tasks.ingestion_tasks import _fail_retryable
        job, db = _make_job(), MagicMock()
        _fail_retryable(job, db, "m", "t")
        db.commit.assert_called_once()



class TestStageHash:
    def test_returns_64_char_hex(self, tmp_path):
        from tasks.ingestion_tasks import _stage_hash
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"hello chatpaper")
        result = _stage_hash(f)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_correct_sha256(self, tmp_path):
        from tasks.ingestion_tasks import _stage_hash
        data = b"deterministic content"
        f = tmp_path / "doc.txt"
        f.write_bytes(data)
        assert _stage_hash(f) == hashlib.sha256(data).hexdigest()

    def test_deterministic_for_same_file(self, tmp_path):
        from tasks.ingestion_tasks import _stage_hash
        f = tmp_path / "same.txt"
        f.write_bytes(b"same bytes")
        assert _stage_hash(f) == _stage_hash(f)

    def test_different_contents_produce_different_hashes(self, tmp_path):
        from tasks.ingestion_tasks import _stage_hash
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"alpha")
        f2.write_bytes(b"beta")
        assert _stage_hash(f1) != _stage_hash(f2)



class TestStageParentChunk:
    def _mock_splitter(self, mocker, chunks: list[str]):
        cls = mocker.patch("tasks.ingestion_tasks.RecursiveCharacterTextSplitter")
        cls.return_value.split_text.return_value = chunks
        return cls

    def test_returns_list_of_parent_chunks(self, mocker):
        from tasks.ingestion_tasks import _stage_parent_chunk, ParentChunk
        self._mock_splitter(mocker, ["hello world"])
        result = _stage_parent_chunk([_make_parsed_element("hello world")])
        assert len(result) == 1
        assert isinstance(result[0], ParentChunk)

    def test_uses_parent_chunk_size_from_settings(self, mocker):
        from tasks.ingestion_tasks import _stage_parent_chunk
        from core.config import settings
        cls = self._mock_splitter(mocker, [])
        _stage_parent_chunk([_make_parsed_element("text")])
        assert cls.call_args.kwargs["chunk_size"] == settings.parent_chunk_size

    def test_uses_parent_chunk_overlap_from_settings(self, mocker):
        from tasks.ingestion_tasks import _stage_parent_chunk
        from core.config import settings
        cls = self._mock_splitter(mocker, [])
        _stage_parent_chunk([_make_parsed_element("text")])
        assert cls.call_args.kwargs["chunk_overlap"] == settings.parent_chunk_overlap

    def test_empty_list_returns_empty(self, mocker):
        from tasks.ingestion_tasks import _stage_parent_chunk
        self._mock_splitter(mocker, [])
        assert _stage_parent_chunk([]) == []

    def test_table_element_is_atomic(self, mocker):
        from tasks.ingestion_tasks import _stage_parent_chunk
        self._mock_splitter(mocker, [])
        el = _make_parsed_element("| a | b |", page=2, etype="Table")
        result = _stage_parent_chunk([el])
        assert len(result) == 1
        assert result[0].element_types == "Table"
        assert result[0].page_start == 2
        assert result[0].page_end == 2

    def test_chunk_index_increments(self, mocker):
        from tasks.ingestion_tasks import _stage_parent_chunk
        self._mock_splitter(mocker, ["part1", "part2"])
        result = _stage_parent_chunk([_make_parsed_element("part1 part2")])
        assert [c.chunk_index for c in result] == list(range(len(result)))



class TestStageChildChunk:
    def _mock_splitter(self, mocker, children: list[str]):
        cls = mocker.patch("tasks.ingestion_tasks.RecursiveCharacterTextSplitter")
        cls.return_value.split_text.return_value = children
        return cls

    def test_returns_generator(self, mocker):
        from tasks.ingestion_tasks import _stage_child_chunk
        self._mock_splitter(mocker, ["c1"])
        result = _stage_child_chunk([_make_parent_chunk()])
        assert isinstance(result, types.GeneratorType)

    def test_one_tuple_per_parent(self, mocker):
        from tasks.ingestion_tasks import _stage_child_chunk
        self._mock_splitter(mocker, ["c"])
        pairs = list(_stage_child_chunk([
            _make_parent_chunk("p1", 0),
            _make_parent_chunk("p2", 1),
        ]))
        assert len(pairs) == 2

    def test_empty_parents_returns_empty(self, mocker):
        from tasks.ingestion_tasks import _stage_child_chunk
        self._mock_splitter(mocker, [])
        assert list(_stage_child_chunk([])) == []

    def test_table_parent_passes_through_unchanged(self, mocker):
        from tasks.ingestion_tasks import _stage_child_chunk
        cls = self._mock_splitter(mocker, ["should not be called"])
        parent = _make_parent_chunk("| col1 | col2 |", etype="Table")
        pairs = list(_stage_child_chunk([parent]))
        assert pairs[0][1] == ["| col1 | col2 |"]
        cls.return_value.split_text.assert_not_called()

    def test_uses_child_chunk_size_from_settings(self, mocker):
        from tasks.ingestion_tasks import _stage_child_chunk
        from core.config import settings
        cls = self._mock_splitter(mocker, [])
        list(_stage_child_chunk([_make_parent_chunk()]))
        assert cls.call_args.kwargs["chunk_size"] == settings.child_chunk_size

    def test_uses_child_chunk_overlap_from_settings(self, mocker):
        from tasks.ingestion_tasks import _stage_child_chunk
        from core.config import settings
        cls = self._mock_splitter(mocker, [])
        list(_stage_child_chunk([_make_parent_chunk()]))
        assert cls.call_args.kwargs["chunk_overlap"] == settings.child_chunk_overlap



class TestStageEmbedUpsert:
    def _patch(self, mocker, embeddings=None):
        if embeddings is None:
            embeddings = [[0.1, 0.2, 0.3]]
        mock_emb = MagicMock()
        mock_emb.embed_documents.return_value = embeddings
        mocker.patch("tasks.ingestion_tasks.get_embedder", return_value=mock_emb)

        collection = MagicMock()
        mocker.patch("tasks.ingestion_tasks.get_child_chunks_collection", return_value=collection)

        db = MagicMock()
        # DocumentParent lookup returns None → is_committed skip does not fire
        db.query.return_value.filter.return_value.first.return_value = None

        return mock_emb, collection, db

    def _call(self, db, mocker, file_id=1, user_id=2, file_hash="hash",
              filename="f.pdf", file_type="application/pdf", language="en",
              pairs=None):
        from tasks.ingestion_tasks import _stage_embed_upsert
        if pairs is None:
            pairs = [(_make_parent_chunk(), ["child"])]
        _stage_embed_upsert(file_id, user_id, file_hash, filename, file_type, language, iter(pairs), db)

    def test_upserts_to_collection(self, mocker):
        _, col, db = self._patch(mocker)
        self._call(db, mocker)
        col.upsert.assert_called_once()

    def test_merges_parent_row_to_db(self, mocker):
        _, _, db = self._patch(mocker)
        self._call(db, mocker)
        db.merge.assert_called_once()

    def test_commits_db(self, mocker):
        _, _, db = self._patch(mocker)
        self._call(db, mocker)
        db.commit.assert_called_once()

    def test_one_merge_per_parent(self, mocker):
        _, _, db = self._patch(mocker, embeddings=[[0.1]])
        self._call(db, mocker, pairs=[
            (_make_parent_chunk("p1", 0), ["c"]),
            (_make_parent_chunk("p2", 1), ["c"]),
            (_make_parent_chunk("p3", 2), ["c"]),
        ])
        assert db.merge.call_count == 3

    def test_parent_id_is_sha256_of_hash_and_index(self, mocker):
        _, _, db = self._patch(mocker)
        self._call(db, mocker, file_hash="abc", pairs=[(_make_parent_chunk(chunk_index=0), ["child"])])
        merged_obj = db.merge.call_args[0][0]
        assert merged_obj.id == hashlib.sha256(b"abc:0").hexdigest()

    def test_skips_upsert_when_no_children(self, mocker):
        _, col, db = self._patch(mocker)
        self._call(db, mocker, pairs=[(_make_parent_chunk(), [])])
        col.upsert.assert_not_called()

    def test_child_metadata_contains_file_id(self, mocker):
        _, col, db = self._patch(mocker)
        self._call(db, mocker, file_id=42)
        metadatas = col.upsert.call_args.kwargs["metadatas"]
        assert metadatas[0]["file_id"] == 42

    def test_is_committed_parent_is_skipped(self, mocker):
        _, col, db = self._patch(mocker)
        committed = MagicMock()
        committed.is_committed = True
        db.query.return_value.filter.return_value.first.return_value = committed
        self._call(db, mocker)
        col.upsert.assert_not_called()



class TestStageSummarize:
    def _patch(self, mocker, summary: str = "A great document summary."):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = summary
        mocker.patch("tasks.ingestion_tasks.get_chat_llm", return_value=mock_llm)

        mock_emb = MagicMock()
        mock_emb.embed_documents.return_value = [[0.5, 0.6]]
        mocker.patch("tasks.ingestion_tasks.get_embedder", return_value=mock_emb)

        mocker.patch(
            "tasks.ingestion_tasks.SystemMessage",
            side_effect=lambda content: {"role": "system", "content": content},
        )
        mocker.patch(
            "tasks.ingestion_tasks.HumanMessage",
            side_effect=lambda content: {"role": "user", "content": content},
        )

        col = MagicMock()
        mocker.patch("tasks.ingestion_tasks.get_document_summaries_collection", return_value=col)
        return mock_llm, mock_emb, col

    def _call(self, mocker, file_id=1, user_id=2, file_hash="hash",
              filename="test.pdf", language="en", text="document text"):
        from tasks.ingestion_tasks import _stage_summarize
        _, _, col = self._patch(mocker)
        _stage_summarize(file_id, user_id, file_hash, filename, language, text)
        return col

    def test_upserts_to_collection(self, mocker):
        from tasks.ingestion_tasks import _stage_summarize
        _, _, col = self._patch(mocker)
        _stage_summarize(1, 2, "hash", "test.pdf", "en", "document text")
        col.upsert.assert_called_once()

    def test_summary_id_format(self, mocker):
        from tasks.ingestion_tasks import _stage_summarize
        _, _, col = self._patch(mocker)
        _stage_summarize(1, 2, "myhash", "test.pdf", "en", "text")
        assert col.upsert.call_args.kwargs["ids"] == ["summary:myhash"]

    def test_metadata_includes_file_id(self, mocker):
        from tasks.ingestion_tasks import _stage_summarize
        _, _, col = self._patch(mocker)
        _stage_summarize(99, 2, "h", "test.pdf", "en", "text")
        assert col.upsert.call_args.kwargs["metadatas"][0]["file_id"] == 99

    def test_metadata_includes_file_hash(self, mocker):
        from tasks.ingestion_tasks import _stage_summarize
        _, _, col = self._patch(mocker)
        _stage_summarize(1, 2, "abc123", "test.pdf", "en", "text")
        assert col.upsert.call_args.kwargs["metadatas"][0]["file_hash"] == "abc123"

    def test_llm_invoked_once_for_short_doc(self, mocker):
        from tasks.ingestion_tasks import _stage_summarize
        llm, _, _ = self._patch(mocker)
        _stage_summarize(1, 2, "h", "f.pdf", "en", "short text")
        llm.invoke.assert_called_once()

    def test_map_reduce_path_makes_multiple_llm_calls(self, mocker):
        from tasks.ingestion_tasks import _stage_summarize
        from core.config import settings
        llm, _, _ = self._patch(mocker)
        long_text = "x" * (settings.summary_short_doc_threshold + 1)
        _stage_summarize(1, 2, "h", "f.pdf", "en", long_text)
        expected_windows = -(-len(long_text) // settings.summary_window_size)  # ceiling div
        assert llm.invoke.call_count == expected_windows + 1



class TestRunIngestionOrchestrator:
    """Tests for run_ingestion Celery task. All stages and I/O are mocked."""

    def _patch_happy_stages(self, mocker, tmp_path: Path, filename: str = "abc_test.pdf"):
        (tmp_path / filename).write_bytes(b"PDF content")
        mocker.patch("tasks.ingestion_tasks.FILES_DIR", tmp_path)
        mocker.patch(
            "tasks.ingestion_tasks._stage_parse",
            return_value=[_make_parsed_element("parsed text")],
        )
        mocker.patch("tasks.ingestion_tasks._stage_hash", return_value="a" * 64)
        mocker.patch(
            "tasks.ingestion_tasks._stage_parent_chunk",
            return_value=[_make_parent_chunk("p1", 0), _make_parent_chunk("p2", 1)],
        )
        mocker.patch(
            "tasks.ingestion_tasks._stage_child_chunk",
            return_value=iter([
                (_make_parent_chunk("p1", 0), ["c1"]),
                (_make_parent_chunk("p2", 1), ["c2"]),
            ]),
        )
        mocker.patch("tasks.ingestion_tasks._stage_embed_upsert")
        mocker.patch("tasks.ingestion_tasks._stage_summarize")

    # happy path

    def test_happy_path_returns_complete_status(self, mocker, tmp_path):
        from tasks.ingestion_tasks import run_ingestion
        _make_db_mock(mocker, _make_job(), _make_file_record())
        self._patch_happy_stages(mocker, tmp_path)
        assert run_ingestion(1, 10)["status"] == "COMPLETE"

    def test_happy_path_returns_chunk_count(self, mocker, tmp_path):
        from tasks.ingestion_tasks import run_ingestion
        _make_db_mock(mocker, _make_job(), _make_file_record())
        self._patch_happy_stages(mocker, tmp_path)
        assert run_ingestion(1, 10)["chunks"] == 2

    def test_all_six_stages_called(self, mocker, tmp_path):
        import tasks.ingestion_tasks as t
        from tasks.ingestion_tasks import run_ingestion
        _make_db_mock(mocker, _make_job(), _make_file_record())
        self._patch_happy_stages(mocker, tmp_path)
        run_ingestion(1, 10)
        t._stage_parse.assert_called_once()
        t._stage_hash.assert_called_once()
        t._stage_parent_chunk.assert_called_once()
        t._stage_child_chunk.assert_called_once()
        t._stage_embed_upsert.assert_called_once()
        t._stage_summarize.assert_called_once()

    def test_db_closed_after_success(self, mocker, tmp_path):
        from tasks.ingestion_tasks import run_ingestion
        db = _make_db_mock(mocker, _make_job(), _make_file_record())
        self._patch_happy_stages(mocker, tmp_path)
        run_ingestion(1, 10)
        db.close.assert_called_once()

    # missing job

    def test_missing_job_raises_value_error(self, mocker):
        from tasks.ingestion_tasks import run_ingestion
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        mocker.patch("tasks.ingestion_tasks.SessionLocal", return_value=db)
        with pytest.raises(ValueError, match="not found"):
            run_ingestion(999, 1)
        db.close.assert_called_once()

    # missing file record

    def test_missing_file_record_returns_failed_permanent(self, mocker):
        from tasks.ingestion_tasks import run_ingestion
        job = _make_job()
        _make_db_mock(mocker, job, file_record=None)
        result = run_ingestion(1, 10)
        assert result["status"] == "FAILED_PERMANENT"
        assert job.status == IngestionJob.STATUS_FAILED_PERMANENT

    # file not on disk

    def test_file_not_on_disk_returns_failed_permanent(self, mocker, tmp_path):
        from tasks.ingestion_tasks import run_ingestion
        job = _make_job()
        fr = _make_file_record(filepath="/files/no_such_file.pdf")
        _make_db_mock(mocker, job, fr)
        mocker.patch("tasks.ingestion_tasks.FILES_DIR", tmp_path)
        result = run_ingestion(1, 10)
        assert result["status"] == "FAILED_PERMANENT"
        assert result["reason"] == "file_missing_on_disk"

    # empty parse result

    def test_empty_parse_result_returns_failed_permanent(self, mocker, tmp_path):
        from tasks.ingestion_tasks import run_ingestion
        job = _make_job()
        fr = _make_file_record()
        (tmp_path / "abc_test.pdf").write_bytes(b"x")
        mocker.patch("tasks.ingestion_tasks.FILES_DIR", tmp_path)
        mocker.patch("tasks.ingestion_tasks._stage_parse", return_value=[])
        _make_db_mock(mocker, job, fr)
        result = run_ingestion(1, 10)
        assert result["status"] == "FAILED_PERMANENT"
        assert result["reason"] == "empty_document"

    # dedup path

    def test_dedup_returns_complete_with_flag(self, mocker, tmp_path):
        from tasks.ingestion_tasks import run_ingestion
        job = _make_job()
        fr = _make_file_record()
        (tmp_path / "abc_test.pdf").write_bytes(b"content")
        mocker.patch("tasks.ingestion_tasks.FILES_DIR", tmp_path)
        mocker.patch("tasks.ingestion_tasks._stage_parse", return_value=[_make_parsed_element("t")])
        mocker.patch("tasks.ingestion_tasks._stage_hash", return_value="h" * 64)
        _make_db_mock(mocker, job, fr, duplicate_record=MagicMock())
        result = run_ingestion(1, 10)
        assert result["status"] == "COMPLETE"
        assert result["deduped"] is True

    def test_dedup_skips_chunk_stages(self, mocker, tmp_path):
        import tasks.ingestion_tasks as t
        from tasks.ingestion_tasks import run_ingestion
        job = _make_job()
        fr = _make_file_record()
        (tmp_path / "abc_test.pdf").write_bytes(b"content")
        mocker.patch("tasks.ingestion_tasks.FILES_DIR", tmp_path)
        mocker.patch("tasks.ingestion_tasks._stage_parse", return_value=[_make_parsed_element("t")])
        mocker.patch("tasks.ingestion_tasks._stage_hash", return_value="h" * 64)
        pc = mocker.patch("tasks.ingestion_tasks._stage_parent_chunk")
        _make_db_mock(mocker, job, fr, duplicate_record=MagicMock())
        run_ingestion(1, 10)
        pc.assert_not_called()

    # error handling

    def test_db_closed_after_exception(self, mocker, tmp_path):
        from tasks.ingestion_tasks import run_ingestion
        db = _make_db_mock(mocker, _make_job(), _make_file_record())
        self._patch_happy_stages(mocker, tmp_path)
        mocker.patch("tasks.ingestion_tasks._stage_parse", side_effect=RuntimeError("parse boom"))
        mocker.patch.object(run_ingestion, "retry", side_effect=RuntimeError("retry blocked"))
        with pytest.raises(RuntimeError):
            run_ingestion(1, 10)
        db.close.assert_called_once()

    def test_exception_marks_job_retryable_when_retries_remain(self, mocker, tmp_path):
        from tasks.ingestion_tasks import run_ingestion
        job = _make_job(retry_count=0)
        fr = _make_file_record()
        (tmp_path / "abc_test.pdf").write_bytes(b"x")
        mocker.patch("tasks.ingestion_tasks.FILES_DIR", tmp_path)
        mocker.patch("tasks.ingestion_tasks._stage_parse", side_effect=IOError("disk error"))
        _make_db_mock(mocker, job, fr)
        mocker.patch.object(run_ingestion, "retry", side_effect=RuntimeError("retry blocked"))
        with pytest.raises((IOError, RuntimeError)):
            run_ingestion(1, 10)
        assert job.status == IngestionJob.STATUS_FAILED_RETRYABLE

    def test_exception_marks_job_permanent_at_max_retries(self, mocker, tmp_path):
        from tasks.ingestion_tasks import run_ingestion
        job = _make_job(retry_count=0)
        fr = _make_file_record()
        (tmp_path / "abc_test.pdf").write_bytes(b"x")
        mocker.patch("tasks.ingestion_tasks.FILES_DIR", tmp_path)
        mocker.patch("tasks.ingestion_tasks._stage_parse", side_effect=RuntimeError("persistent error"))
        _make_db_mock(mocker, job, fr)
        original_max = run_ingestion.max_retries
        run_ingestion.max_retries = 0
        try:
            with pytest.raises(RuntimeError):
                run_ingestion(1, 10)
        finally:
            run_ingestion.max_retries = original_max
        assert job.status == IngestionJob.STATUS_FAILED_PERMANENT

    def test_db_rolled_back_before_status_update(self, mocker, tmp_path):
        from tasks.ingestion_tasks import run_ingestion
        job = _make_job()
        fr = _make_file_record()
        db = _make_db_mock(mocker, job, fr)
        (tmp_path / "abc_test.pdf").write_bytes(b"x")
        mocker.patch("tasks.ingestion_tasks.FILES_DIR", tmp_path)
        mocker.patch("tasks.ingestion_tasks._stage_parse", side_effect=ValueError("bad"))
        mocker.patch.object(run_ingestion, "retry", side_effect=ValueError("no retry"))
        with pytest.raises(ValueError):
            run_ingestion(1, 10)
        db.rollback.assert_called_once()

    def test_scanned_pdf_returns_failed_permanent(self, mocker, tmp_path):
        from tasks.ingestion_tasks import run_ingestion
        job = _make_job()
        fr = _make_file_record()
        # file must exceed scanned_pdf_min_file_size_bytes (default 51200) with near-zero text
        big_file = tmp_path / "abc_test.pdf"
        big_file.write_bytes(b"\x00" * 52_000)
        mocker.patch("tasks.ingestion_tasks.FILES_DIR", tmp_path)
        mocker.patch(
            "tasks.ingestion_tasks._stage_parse",
            return_value=[_make_parsed_element("x")],  # 1 char / 52000 bytes → well below threshold
        )
        _make_db_mock(mocker, job, fr)
        result = run_ingestion(1, 10)
        assert result["status"] == "FAILED_PERMANENT"
        assert result["reason"] == "likely_scanned_pdf"



class TestParseTabular:
    def test_csv_returns_parsed_elements(self, tmp_path):
        from tasks.ingestion_tasks import _parse_tabular
        f = tmp_path / "data.csv"
        f.write_text("col1,col2\na,b\nc,d\n")
        result = _parse_tabular(f, "text/csv")
        assert len(result) >= 1
        assert result[0].element_type == "Table"

    def test_csv_chunks_at_50_row_boundary(self, tmp_path):
        from tasks.ingestion_tasks import _parse_tabular
        rows = ["col1,col2"] + [f"{i},{i + 1}" for i in range(120)]
        f = tmp_path / "big.csv"
        f.write_text("\n".join(rows))
        result = _parse_tabular(f, "text/csv")
        assert len(result) == 3  # 50 + 50 + 20

    def test_csv_content_contains_headers(self, tmp_path):
        from tasks.ingestion_tasks import _parse_tabular
        f = tmp_path / "data.csv"
        f.write_text("name,age\nAlice,30\nBob,25\n")
        result = _parse_tabular(f, "text/csv")
        assert "name" in result[0].text
        assert "age" in result[0].text

    def test_csv_no_data_rows_raises_value_error(self, tmp_path):
        from tasks.ingestion_tasks import _parse_tabular
        f = tmp_path / "empty.csv"
        f.write_text("col1,col2\n")
        with pytest.raises(ValueError, match="no data rows"):
            _parse_tabular(f, "text/csv")

    def test_malformed_csv_raises_value_error(self, tmp_path):
        import pandas as pd
        from tasks.ingestion_tasks import _parse_tabular
        f = tmp_path / "bad.csv"
        f.write_text("col1,col2\na,b\n")
        with patch("pandas.read_csv", side_effect=pd.errors.ParserError("bad")):
            with pytest.raises(ValueError, match="malformed"):
                _parse_tabular(f, "text/csv")

    def test_all_na_rows_dropped(self, tmp_path):
        from tasks.ingestion_tasks import _parse_tabular
        f = tmp_path / "na.csv"
        # first data row is all-NA; second has real values
        f.write_text("col1,col2\n,\na,b\n")
        result = _parse_tabular(f, "text/csv")
        assert len(result) == 1



class TestStageParse:
    def test_tabular_dispatch_for_csv(self, mocker, tmp_path):
        from tasks.ingestion_tasks import _stage_parse
        f = tmp_path / "data.csv"
        f.write_bytes(b"a,b\n1,2\n")
        mock_tab = mocker.patch("tasks.ingestion_tasks._parse_tabular", return_value=[])
        _stage_parse(f, "text/csv")
        mock_tab.assert_called_once_with(f, "text/csv")

    def test_tabular_dispatch_for_xlsx(self, mocker, tmp_path):
        from tasks.ingestion_tasks import _stage_parse
        f = tmp_path / "data.xlsx"
        f.write_bytes(b"fake")
        mock_tab = mocker.patch("tasks.ingestion_tasks._parse_tabular", return_value=[])
        _stage_parse(f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        mock_tab.assert_called_once()

    def test_chardet_high_confidence_passes_detected_encoding(self, mocker, tmp_path):
        from tasks.ingestion_tasks import _stage_parse
        f = tmp_path / "doc.txt"
        f.write_bytes(b"hello world")
        mocker.patch("chardet.detect", return_value={"encoding": "windows-1252", "confidence": 0.95})
        mock_part = mocker.patch("unstructured.partition.auto.partition", return_value=[])
        _stage_parse(f, "text/plain")
        assert mock_part.call_args.kwargs.get("encoding") == "windows-1252"

    def test_chardet_low_confidence_falls_back_to_utf8(self, mocker, tmp_path):
        from tasks.ingestion_tasks import _stage_parse
        f = tmp_path / "doc.txt"
        f.write_bytes(b"hello world")
        mocker.patch("chardet.detect", return_value={"encoding": "ascii", "confidence": 0.4})
        mock_part = mocker.patch("unstructured.partition.auto.partition", return_value=[])
        _stage_parse(f, "text/plain")
        assert mock_part.call_args.kwargs.get("encoding") == "utf-8"



class TestStageParentChunkMetadata:
    def test_page_range_derived_from_elements(self, mocker):
        from tasks.ingestion_tasks import _stage_parent_chunk
        cls = mocker.patch("tasks.ingestion_tasks.RecursiveCharacterTextSplitter")
        cls.return_value.split_text.return_value = ["text from page 5"]
        result = _stage_parent_chunk([_make_parsed_element("text from page 5", page=5)])
        assert result[0].page_start == 5
        assert result[0].page_end == 5

    def test_element_types_collected_per_chunk(self, mocker):
        from tasks.ingestion_tasks import _stage_parent_chunk
        cls = mocker.patch("tasks.ingestion_tasks.RecursiveCharacterTextSplitter")
        cls.return_value.split_text.return_value = ["title text"]
        result = _stage_parent_chunk([_make_parsed_element("title text", etype="Title")])
        assert "Title" in result[0].element_types

    def test_multi_element_chunk_spans_page_range(self, mocker):
        from tasks.ingestion_tasks import _stage_parent_chunk, ParsedElement
        cls = mocker.patch("tasks.ingestion_tasks.RecursiveCharacterTextSplitter")
        els = [
            _make_parsed_element("page two text", page=2, etype="NarrativeText"),
            _make_parsed_element("page four text", page=4, etype="NarrativeText"),
        ]
        combined = "page two text\n\npage four text"
        cls.return_value.split_text.return_value = [combined]
        result = _stage_parent_chunk(els)
        assert result[0].page_start == 2
        assert result[0].page_end == 4



class TestStageEmbedUpsertMetadata:
    def _patch(self, mocker):
        mock_emb = MagicMock()
        mock_emb.embed_documents.return_value = [[0.1, 0.2]]
        mocker.patch("tasks.ingestion_tasks.get_embedder", return_value=mock_emb)
        col = MagicMock()
        mocker.patch("tasks.ingestion_tasks.get_child_chunks_collection", return_value=col)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        return col, db

    def _call(self, col, db, **kw):
        from tasks.ingestion_tasks import _stage_embed_upsert
        defaults = dict(
            file_id=1, user_id=2, file_hash="h",
            filename="f.pdf", file_type="application/pdf",
            language="en", pairs=[(_make_parent_chunk(), ["c"])],
        )
        defaults.update(kw)
        _stage_embed_upsert(
            defaults["file_id"], defaults["user_id"], defaults["file_hash"],
            defaults["filename"], defaults["file_type"], defaults["language"],
            iter(defaults["pairs"]), db,
        )
        return col.upsert.call_args.kwargs["metadatas"][0]

    def test_metadata_contains_user_id(self, mocker):
        col, db = self._patch(mocker)
        meta = self._call(col, db, user_id=77)
        assert meta["user_id"] == 77

    def test_metadata_contains_language(self, mocker):
        col, db = self._patch(mocker)
        meta = self._call(col, db, language="de")
        assert meta["language"] == "de"

    def test_metadata_contains_filename(self, mocker):
        col, db = self._patch(mocker)
        meta = self._call(col, db, filename="report.pdf")
        assert meta["filename"] == "report.pdf"

    def test_metadata_contains_page_range(self, mocker):
        col, db = self._patch(mocker)
        from tasks.ingestion_tasks import ParentChunk
        parent = ParentChunk(text="t", chunk_index=0, page_start=3, page_end=7, element_types="NarrativeText")
        meta = self._call(col, db, pairs=[(parent, ["c"])])
        assert meta["page_start"] == 3
        assert meta["page_end"] == 7

    def test_metadata_contains_element_types(self, mocker):
        col, db = self._patch(mocker)
        parent = _make_parent_chunk(etype="NarrativeText,Title")
        meta = self._call(col, db, pairs=[(parent, ["c"])])
        assert meta["element_types"] == "NarrativeText,Title"



class TestStageExtractPropositions:
    def _patch(self, mocker, llm_response: str = "1. First fact.\n2. Second fact."):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = llm_response
        mocker.patch("tasks.ingestion_tasks.get_chat_llm", return_value=mock_llm)

        mock_emb = MagicMock()
        mock_emb.embed_documents.return_value = [[0.1], [0.2]]
        mocker.patch("tasks.ingestion_tasks.get_embedder", return_value=mock_emb)

        col = MagicMock()
        mocker.patch("tasks.ingestion_tasks.get_propositions_collection", return_value=col)
        mocker.patch(
            "tasks.ingestion_tasks.SystemMessage",
            side_effect=lambda content: {"role": "system", "content": content},
        )
        mocker.patch(
            "tasks.ingestion_tasks.HumanMessage",
            side_effect=lambda content: {"role": "user", "content": content},
        )
        return mock_llm, mock_emb, col

    def _make_db(self, parents):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = parents
        return db

    def _make_db_parent(self, content: str = "Some text.", parent_id: str = "pid1"):
        p = MagicMock()
        p.id = parent_id
        p.content = content
        return p

    def test_upserts_propositions_to_collection(self, mocker):
        from tasks.ingestion_tasks import _stage_extract_propositions
        _, _, col = self._patch(mocker)
        db = self._make_db([self._make_db_parent()])
        _stage_extract_propositions(1, 2, "hash", "f.pdf", "en", db)
        col.upsert.assert_called_once()

    def test_numbering_stripped_from_propositions(self, mocker):
        from tasks.ingestion_tasks import _stage_extract_propositions
        _, _, col = self._patch(mocker, "1. First fact.\n2. Second fact.")
        db = self._make_db([self._make_db_parent()])
        _stage_extract_propositions(1, 2, "hash", "f.pdf", "en", db)
        docs = col.upsert.call_args.kwargs["documents"]
        assert all(not d[0].isdigit() for d in docs)

    def test_empty_llm_response_skips_upsert(self, mocker):
        from tasks.ingestion_tasks import _stage_extract_propositions
        _, _, col = self._patch(mocker, llm_response="")
        db = self._make_db([self._make_db_parent()])
        _stage_extract_propositions(1, 2, "hash", "f.pdf", "en", db)
        col.upsert.assert_not_called()

    def test_one_upsert_per_non_empty_parent(self, mocker):
        from tasks.ingestion_tasks import _stage_extract_propositions
        _, emb, col = self._patch(mocker, "Fact one.")
        emb.embed_documents.return_value = [[0.1]]
        parents = [self._make_db_parent("A", "p1"), self._make_db_parent("B", "p2")]
        db = self._make_db(parents)
        _stage_extract_propositions(1, 2, "hash", "f.pdf", "en", db)
        assert col.upsert.call_count == 2

    def test_proposition_ids_reference_parent_id(self, mocker):
        from tasks.ingestion_tasks import _stage_extract_propositions
        _, emb, col = self._patch(mocker, "A single fact.")
        emb.embed_documents.return_value = [[0.1]]
        db = self._make_db([self._make_db_parent("text", "abc123")])
        _stage_extract_propositions(1, 2, "hash", "f.pdf", "en", db)
        ids = col.upsert.call_args.kwargs["ids"]
        assert all("abc123" in id_ for id_ in ids)
