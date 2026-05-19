"""Unit tests for the ingestion pipeline. All external I/O is mocked."""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from models.ingestion import IngestionJob


# helpers

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
    fr.filepath = filepath
    fr.file_type = file_type
    fr.total_pages = None
    fr.file_hash = None
    fr.ingestion_status = None
    return fr


def _make_db_mock(mocker, job, file_record, existing_parent=None):
    # returns the right mock per model class instead of relying on call-order side_effect
    from models.file_model import FileRecord
    from models.ingestion import DocumentParent, IngestionJob as IJ

    def _query(model):
        q = MagicMock()
        if model is IJ:
            q.filter.return_value.first.return_value = job
        elif model is FileRecord:
            q.filter.return_value.first.return_value = file_record
        elif model is DocumentParent:
            q.filter.return_value.first.return_value = existing_parent
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

    def test_returns_list_of_strings(self, mocker):
        from tasks.ingestion_tasks import _stage_parent_chunk
        self._mock_splitter(mocker, ["chunk A", "chunk B"])
        assert _stage_parent_chunk("some text") == ["chunk A", "chunk B"]

    def test_uses_parent_chunk_size_from_settings(self, mocker):
        from tasks.ingestion_tasks import _stage_parent_chunk
        from core.config import settings
        cls = self._mock_splitter(mocker, [])
        _stage_parent_chunk("text")
        assert cls.call_args.kwargs["chunk_size"] == settings.parent_chunk_size

    def test_uses_parent_chunk_overlap_from_settings(self, mocker):
        from tasks.ingestion_tasks import _stage_parent_chunk
        from core.config import settings
        cls = self._mock_splitter(mocker, [])
        _stage_parent_chunk("text")
        assert cls.call_args.kwargs["chunk_overlap"] == settings.parent_chunk_overlap

    def test_empty_text_returns_splitter_result(self, mocker):
        from tasks.ingestion_tasks import _stage_parent_chunk
        self._mock_splitter(mocker, [])
        assert _stage_parent_chunk("") == []



class TestStageChildChunk:
    def _mock_splitter(self, mocker, children: list[str]):
        cls = mocker.patch("tasks.ingestion_tasks.RecursiveCharacterTextSplitter")
        cls.return_value.split_text.return_value = children
        return cls

    def test_returns_list_of_tuples(self, mocker):
        from tasks.ingestion_tasks import _stage_child_chunk
        self._mock_splitter(mocker, ["c1", "c2"])
        result = _stage_child_chunk(["parent"])
        assert result == [("parent", ["c1", "c2"])]

    def test_one_tuple_per_parent(self, mocker):
        from tasks.ingestion_tasks import _stage_child_chunk
        self._mock_splitter(mocker, ["c"])
        result = _stage_child_chunk(["p1", "p2", "p3"])
        assert len(result) == 3

    def test_empty_parents_returns_empty(self, mocker):
        from tasks.ingestion_tasks import _stage_child_chunk
        self._mock_splitter(mocker, [])
        assert _stage_child_chunk([]) == []

    def test_uses_child_chunk_size_from_settings(self, mocker):
        from tasks.ingestion_tasks import _stage_child_chunk
        from core.config import settings
        cls = self._mock_splitter(mocker, [])
        _stage_child_chunk(["p"])
        assert cls.call_args.kwargs["chunk_size"] == settings.child_chunk_size

    def test_uses_child_chunk_overlap_from_settings(self, mocker):
        from tasks.ingestion_tasks import _stage_child_chunk
        from core.config import settings
        cls = self._mock_splitter(mocker, [])
        _stage_child_chunk(["p"])
        assert cls.call_args.kwargs["chunk_overlap"] == settings.child_chunk_overlap



class TestStageEmbedUpsert:
    def _patch(self, mocker, embeddings=None):
        if embeddings is None:
            embeddings = [[0.1, 0.2, 0.3]]
        emb_cls = mocker.patch("tasks.ingestion_tasks.OpenAIEmbeddings")
        emb_cls.return_value.embed_documents.return_value = embeddings

        collection = MagicMock()
        mocker.patch("tasks.ingestion_tasks.get_child_chunks_collection", return_value=collection)
        return emb_cls.return_value, collection

    def test_upserts_to_collection(self, mocker):
        from tasks.ingestion_tasks import _stage_embed_upsert
        _, col = self._patch(mocker)
        db = MagicMock()
        _stage_embed_upsert(1, "hash", [("parent", ["child"])], db)
        col.upsert.assert_called_once()

    def test_merges_parent_row_to_db(self, mocker):
        from tasks.ingestion_tasks import _stage_embed_upsert
        self._patch(mocker)
        db = MagicMock()
        _stage_embed_upsert(1, "hash", [("parent", ["child"])], db)
        db.merge.assert_called_once()

    def test_commits_db(self, mocker):
        from tasks.ingestion_tasks import _stage_embed_upsert
        self._patch(mocker)
        db = MagicMock()
        _stage_embed_upsert(1, "hash", [("p", ["c"])], db)
        db.commit.assert_called_once()

    def test_one_merge_per_parent(self, mocker):
        from tasks.ingestion_tasks import _stage_embed_upsert
        emb, _ = self._patch(mocker, embeddings=[[0.1]])
        db = MagicMock()
        _stage_embed_upsert(1, "h", [("p1", ["c"]), ("p2", ["c"]), ("p3", ["c"])], db)
        assert db.merge.call_count == 3

    def test_parent_id_is_sha256_of_hash_and_index(self, mocker):
        from tasks.ingestion_tasks import _stage_embed_upsert
        self._patch(mocker)
        db = MagicMock()
        _stage_embed_upsert(1, "abc", [("parent text", ["child"])], db)

        merged_obj = db.merge.call_args[0][0]
        expected_id = hashlib.sha256(b"abc:0").hexdigest()
        assert merged_obj.id == expected_id

    def test_skips_upsert_when_no_children(self, mocker):
        from tasks.ingestion_tasks import _stage_embed_upsert
        _, col = self._patch(mocker)
        db = MagicMock()
        _stage_embed_upsert(1, "h", [("parent", [])], db)
        col.upsert.assert_not_called()

    def test_child_metadata_contains_file_id(self, mocker):
        from tasks.ingestion_tasks import _stage_embed_upsert
        _, col = self._patch(mocker)
        db = MagicMock()
        _stage_embed_upsert(42, "h", [("p", ["c"])], db)
        metadatas = col.upsert.call_args.kwargs["metadatas"]
        assert metadatas[0]["file_id"] == 42



class TestStageSummarize:
    def _patch(self, mocker, summary: str = "A great document summary."):
        llm_cls = mocker.patch("tasks.ingestion_tasks.ChatOpenAI")
        llm_cls.return_value.invoke.return_value.content = summary

        emb_cls = mocker.patch("tasks.ingestion_tasks.OpenAIEmbeddings")
        emb_cls.return_value.embed_documents.return_value = [[0.5, 0.6]]

        mocker.patch("tasks.ingestion_tasks.SystemMessage", side_effect=lambda content: {"role": "system", "content": content})
        mocker.patch("tasks.ingestion_tasks.HumanMessage", side_effect=lambda content: {"role": "user", "content": content})

        col = MagicMock()
        mocker.patch("tasks.ingestion_tasks.get_document_summaries_collection", return_value=col)
        return llm_cls.return_value, emb_cls.return_value, col

    def test_upserts_to_collection(self, mocker):
        from tasks.ingestion_tasks import _stage_summarize
        _, _, col = self._patch(mocker)
        _stage_summarize(1, "hash", "document text")
        col.upsert.assert_called_once()

    def test_summary_id_format(self, mocker):
        from tasks.ingestion_tasks import _stage_summarize
        _, _, col = self._patch(mocker)
        _stage_summarize(1, "myhash", "text")
        ids = col.upsert.call_args.kwargs["ids"]
        assert ids == ["summary:myhash"]

    def test_metadata_includes_file_id(self, mocker):
        from tasks.ingestion_tasks import _stage_summarize
        _, _, col = self._patch(mocker)
        _stage_summarize(99, "h", "text")
        metas = col.upsert.call_args.kwargs["metadatas"]
        assert metas[0]["file_id"] == 99

    def test_metadata_includes_file_hash(self, mocker):
        from tasks.ingestion_tasks import _stage_summarize
        _, _, col = self._patch(mocker)
        _stage_summarize(1, "abc123", "text")
        metas = col.upsert.call_args.kwargs["metadatas"]
        assert metas[0]["file_hash"] == "abc123"

    def test_llm_invoked_once(self, mocker):
        from tasks.ingestion_tasks import _stage_summarize
        llm, _, _ = self._patch(mocker)
        _stage_summarize(1, "h", "text")
        llm.invoke.assert_called_once()

    def test_text_truncated_to_12000_chars(self, mocker):
        from tasks.ingestion_tasks import _stage_summarize
        llm, _, _ = self._patch(mocker)
        long_text = "x" * 20_000
        _stage_summarize(1, "h", long_text)
        messages = llm.invoke.call_args[0][0]
        # HumanMessage mock returns {"role": "user", "content": <text>}
        human_content = messages[-1]["content"]
        assert len(human_content) <= 12_000



class TestRunIngestionOrchestrator:
    """Tests for run_ingestion Celery task. All stages and I/O are mocked."""

    def _patch_happy_stages(self, mocker, tmp_path: Path, filename: str = "abc_test.pdf"):
        (tmp_path / filename).write_bytes(b"PDF content")
        mocker.patch("tasks.ingestion_tasks.FILES_DIR", tmp_path)
        mocker.patch("tasks.ingestion_tasks._stage_parse", return_value=("parsed text", 3, ["Title"]))
        mocker.patch("tasks.ingestion_tasks._stage_hash", return_value="a" * 64)
        mocker.patch("tasks.ingestion_tasks._stage_parent_chunk", return_value=["p1", "p2"])
        mocker.patch("tasks.ingestion_tasks._stage_child_chunk", return_value=[("p1", ["c1"]), ("p2", ["c2"])])
        mocker.patch("tasks.ingestion_tasks._stage_embed_upsert")
        mocker.patch("tasks.ingestion_tasks._stage_summarize")

    # happy path

    def test_happy_path_returns_complete_status(self, mocker, tmp_path):
        from tasks.ingestion_tasks import run_ingestion
        job = _make_job()
        fr = _make_file_record()
        _make_db_mock(mocker, job, fr, existing_parent=None)
        self._patch_happy_stages(mocker, tmp_path)

        result = run_ingestion(1, 10)
        assert result["status"] == "COMPLETE"

    def test_happy_path_returns_chunk_count(self, mocker, tmp_path):
        from tasks.ingestion_tasks import run_ingestion
        job = _make_job()
        fr = _make_file_record()
        _make_db_mock(mocker, job, fr, existing_parent=None)
        self._patch_happy_stages(mocker, tmp_path)

        result = run_ingestion(1, 10)
        assert result["chunks"] == 2  # two parent texts from mock

    def test_all_six_stages_called(self, mocker, tmp_path):
        import tasks.ingestion_tasks as t
        from tasks.ingestion_tasks import run_ingestion
        job = _make_job()
        fr = _make_file_record()
        _make_db_mock(mocker, job, fr, existing_parent=None)
        self._patch_happy_stages(mocker, tmp_path)

        run_ingestion(1, 10)

        t._stage_parse.assert_called_once()
        t._stage_hash.assert_called_once()
        t._stage_parent_chunk.assert_called_once_with("parsed text")
        t._stage_child_chunk.assert_called_once_with(["p1", "p2"])
        t._stage_embed_upsert.assert_called_once()
        t._stage_summarize.assert_called_once()

    def test_db_closed_after_success(self, mocker, tmp_path):
        from tasks.ingestion_tasks import run_ingestion
        job = _make_job()
        fr = _make_file_record()
        db = _make_db_mock(mocker, job, fr, existing_parent=None)
        self._patch_happy_stages(mocker, tmp_path)

        run_ingestion(1, 10)
        db.close.assert_called_once()

    # guard: job not found

    def test_missing_job_raises_value_error(self, mocker):
        from tasks.ingestion_tasks import run_ingestion
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        mocker.patch("tasks.ingestion_tasks.SessionLocal", return_value=db)

        with pytest.raises(ValueError, match="not found"):
            run_ingestion(999, 1)
        db.close.assert_called_once()

    # guard: file record not found

    def test_missing_file_record_returns_failed_permanent(self, mocker):
        from tasks.ingestion_tasks import run_ingestion
        job = _make_job()
        _make_db_mock(mocker, job, file_record=None, existing_parent=None)

        result = run_ingestion(1, 10)
        assert result["status"] == "FAILED_PERMANENT"
        assert job.status == IngestionJob.STATUS_FAILED_PERMANENT

    # guard: file missing on disk

    def test_file_not_on_disk_returns_failed_permanent(self, mocker, tmp_path):
        from tasks.ingestion_tasks import run_ingestion
        job = _make_job()
        fr = _make_file_record(filepath="/files/no_such_file.pdf")
        _make_db_mock(mocker, job, fr, existing_parent=None)
        mocker.patch("tasks.ingestion_tasks.FILES_DIR", tmp_path)

        result = run_ingestion(1, 10)
        assert result["status"] == "FAILED_PERMANENT"
        assert result["reason"] == "file_missing_on_disk"

    # dedup path

    def test_dedup_returns_complete_with_flag(self, mocker, tmp_path):
        from tasks.ingestion_tasks import run_ingestion
        job = _make_job()
        fr = _make_file_record()
        (tmp_path / "abc_test.pdf").write_bytes(b"content")
        mocker.patch("tasks.ingestion_tasks.FILES_DIR", tmp_path)
        mocker.patch("tasks.ingestion_tasks._stage_parse", return_value=("t", 1, []))
        mocker.patch("tasks.ingestion_tasks._stage_hash", return_value="h" * 64)
        _make_db_mock(mocker, job, fr, existing_parent=MagicMock())

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
        mocker.patch("tasks.ingestion_tasks._stage_parse", return_value=("t", 1, []))
        mocker.patch("tasks.ingestion_tasks._stage_hash", return_value="h" * 64)
        pc = mocker.patch("tasks.ingestion_tasks._stage_parent_chunk")
        _make_db_mock(mocker, job, fr, existing_parent=MagicMock())

        run_ingestion(1, 10)
        pc.assert_not_called()

    # error handling

    def test_db_closed_after_exception(self, mocker, tmp_path):
        from tasks.ingestion_tasks import run_ingestion
        job = _make_job()
        fr = _make_file_record()
        db = _make_db_mock(mocker, job, fr, existing_parent=None)
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
        _make_db_mock(mocker, job, fr, existing_parent=None)
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
        _make_db_mock(mocker, job, fr, existing_parent=None)

        # Set max_retries=0 so self.request.retries (0) is NOT < max_retries, triggering permanent failure.
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
        db = _make_db_mock(mocker, job, fr, existing_parent=None)
        (tmp_path / "abc_test.pdf").write_bytes(b"x")
        mocker.patch("tasks.ingestion_tasks.FILES_DIR", tmp_path)
        mocker.patch("tasks.ingestion_tasks._stage_parse", side_effect=ValueError("bad"))
        mocker.patch.object(run_ingestion, "retry", side_effect=ValueError("no retry"))

        with pytest.raises(ValueError):
            run_ingestion(1, 10)
        db.rollback.assert_called_once()
