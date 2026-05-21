"""Unit tests for services/files.py — ingestion job creation and task dispatch on upload."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from models.file_model import FileRecord
from models.ingestion import IngestionJob


def _make_file(filename="paper.pdf", content_type="application/pdf"):
    f = MagicMock()
    f.filename = filename
    f.content_type = content_type
    f.file = MagicMock()
    return f


def _make_user(user_id=1):
    u = MagicMock()
    u.id = user_id
    return u


def _make_db():
    db = MagicMock()

    def _refresh(obj):
        if isinstance(obj, FileRecord):
            obj.id = 42
        elif isinstance(obj, IngestionJob):
            obj.id = 7

    db.refresh.side_effect = _refresh
    return db


class TestUploadFilesIngestionJobCreation:
    def test_creates_ingestion_job_with_queued_status(self, tmp_path):
        db = _make_db()
        with (
            patch("services.files.UPLOAD_DIR", tmp_path),
            patch("services.files.shutil.copyfileobj", lambda src, dst: dst.write(b"x")),
            patch("services.files.run_ingestion") as mock_task,
        ):
            mock_task.delay.return_value = MagicMock(id="task-1")
            from services.files import upload_files
            upload_files(_make_file(), db, _make_user(), "desc")

        added = [c.args[0] for c in db.add.call_args_list]
        jobs = [o for o in added if isinstance(o, IngestionJob)]
        assert len(jobs) == 1
        assert jobs[0].status == IngestionJob.STATUS_QUEUED

    def test_job_file_id_matches_db_record_id(self, tmp_path):
        db = _make_db()
        with (
            patch("services.files.UPLOAD_DIR", tmp_path),
            patch("services.files.shutil.copyfileobj", lambda src, dst: dst.write(b"x")),
            patch("services.files.run_ingestion") as mock_task,
        ):
            mock_task.delay.return_value = MagicMock(id="task-1")
            from services.files import upload_files
            upload_files(_make_file(), db, _make_user(), None)

        added = [c.args[0] for c in db.add.call_args_list]
        jobs = [o for o in added if isinstance(o, IngestionJob)]
        assert jobs[0].file_id == 42  # db_record.id set by _refresh

    def test_dispatches_task_with_job_and_file_ids(self, tmp_path):
        db = _make_db()
        with (
            patch("services.files.UPLOAD_DIR", tmp_path),
            patch("services.files.shutil.copyfileobj", lambda src, dst: dst.write(b"x")),
            patch("services.files.run_ingestion") as mock_task,
        ):
            mock_task.delay.return_value = MagicMock(id="task-1")
            from services.files import upload_files
            upload_files(_make_file(), db, _make_user(), None)

        mock_task.delay.assert_called_once_with(7, 42)  # job.id=7, file_id=42

    def test_task_dispatched_exactly_once(self, tmp_path):
        db = _make_db()
        with (
            patch("services.files.UPLOAD_DIR", tmp_path),
            patch("services.files.shutil.copyfileobj", lambda src, dst: dst.write(b"x")),
            patch("services.files.run_ingestion") as mock_task,
        ):
            mock_task.delay.return_value = MagicMock(id="task-1")
            from services.files import upload_files
            upload_files(_make_file(), db, _make_user(), None)

        assert mock_task.delay.call_count == 1

    def test_stores_celery_task_id_on_job(self, tmp_path):
        db = _make_db()
        with (
            patch("services.files.UPLOAD_DIR", tmp_path),
            patch("services.files.shutil.copyfileobj", lambda src, dst: dst.write(b"x")),
            patch("services.files.run_ingestion") as mock_task,
        ):
            mock_task.delay.return_value = MagicMock(id="celery-abc")
            from services.files import upload_files
            upload_files(_make_file(), db, _make_user(), None)

        added = [c.args[0] for c in db.add.call_args_list]
        jobs = [o for o in added if isinstance(o, IngestionJob)]
        assert jobs[0].celery_task_id == "celery-abc"

    def test_file_record_ingestion_status_is_queued(self, tmp_path):
        db = _make_db()
        with (
            patch("services.files.UPLOAD_DIR", tmp_path),
            patch("services.files.shutil.copyfileobj", lambda src, dst: dst.write(b"x")),
            patch("services.files.run_ingestion") as mock_task,
        ):
            mock_task.delay.return_value = MagicMock(id="task-1")
            from services.files import upload_files
            upload_files(_make_file(), db, _make_user(), None)

        added = [c.args[0] for c in db.add.call_args_list]
        records = [o for o in added if isinstance(o, FileRecord)]
        assert records[0].ingestion_status == IngestionJob.STATUS_QUEUED

    def test_db_committed_at_least_three_times(self, tmp_path):
        db = _make_db()
        with (
            patch("services.files.UPLOAD_DIR", tmp_path),
            patch("services.files.shutil.copyfileobj", lambda src, dst: dst.write(b"x")),
            patch("services.files.run_ingestion") as mock_task,
        ):
            mock_task.delay.return_value = MagicMock(id="task-1")
            from services.files import upload_files
            upload_files(_make_file(), db, _make_user(), None)

        # commit after FileRecord, after IngestionJob, after storing celery_task_id
        assert db.commit.call_count >= 3

    def test_returns_file_record_instance(self, tmp_path):
        db = _make_db()
        with (
            patch("services.files.UPLOAD_DIR", tmp_path),
            patch("services.files.shutil.copyfileobj", lambda src, dst: dst.write(b"x")),
            patch("services.files.run_ingestion") as mock_task,
        ):
            mock_task.delay.return_value = MagicMock(id="task-1")
            from services.files import upload_files
            result = upload_files(_make_file(), db, _make_user(), "my paper")

        assert isinstance(result, FileRecord)


class TestUploadFilesValidation:
    def test_empty_filename_raises_400(self, tmp_path):
        db = MagicMock()
        with patch("services.files.UPLOAD_DIR", tmp_path):
            from services.files import upload_files
            with pytest.raises(HTTPException) as exc_info:
                upload_files(_make_file(filename=""), db, _make_user(), None)
        assert exc_info.value.status_code == 400

    def test_empty_filename_does_not_write_to_disk(self, tmp_path):
        db = MagicMock()
        with (
            patch("services.files.UPLOAD_DIR", tmp_path),
            patch("services.files.shutil.copyfileobj") as mock_copy,
        ):
            from services.files import upload_files
            with pytest.raises(HTTPException):
                upload_files(_make_file(filename=""), db, _make_user(), None)
        mock_copy.assert_not_called()

    def test_empty_filename_does_not_touch_db(self, tmp_path):
        db = MagicMock()
        with patch("services.files.UPLOAD_DIR", tmp_path):
            from services.files import upload_files
            with pytest.raises(HTTPException):
                upload_files(_make_file(filename=""), db, _make_user(), None)
        db.add.assert_not_called()
        db.commit.assert_not_called()
