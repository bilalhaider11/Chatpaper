"""
Phase 1 — test_models_ingestion.py

Verifies ORM model structure for DocumentParent, IngestionJob, and the
five new columns added to FileRecord. Uses __table__ introspection only —
no database connection is required.
"""

import pytest
from sqlalchemy import Integer, String, Text, DateTime

from models.ingestion import DocumentParent, IngestionJob
from models.file_model import FileRecord


# ── DocumentParent ────────────────────────────────────────────────────────────

class TestDocumentParentTable:
    def _cols(self):
        return DocumentParent.__table__.columns

    def test_tablename(self):
        assert DocumentParent.__tablename__ == "document_parents"

    def test_id_column_exists(self):
        assert "id" in self._cols()

    def test_id_is_primary_key(self):
        assert self._cols()["id"].primary_key

    def test_id_is_string_type(self):
        assert isinstance(self._cols()["id"].type, String)

    def test_id_string_length_is_64(self):
        assert self._cols()["id"].type.length == 64

    def test_file_id_column_exists(self):
        assert "file_id" in self._cols()

    def test_file_id_is_not_nullable(self):
        assert not self._cols()["file_id"].nullable

    def test_file_id_has_foreign_key(self):
        fks = list(self._cols()["file_id"].foreign_keys)
        assert len(fks) == 1

    def test_file_id_fk_targets_files_data(self):
        fk = list(self._cols()["file_id"].foreign_keys)[0]
        assert "files_data.id" in str(fk.target_fullname)

    def test_file_id_fk_has_cascade_delete(self):
        fk = list(self._cols()["file_id"].foreign_keys)[0]
        assert fk.ondelete == "CASCADE"

    def test_content_column_exists(self):
        assert "content" in self._cols()

    def test_content_is_text_type(self):
        assert isinstance(self._cols()["content"].type, Text)

    def test_content_is_not_nullable(self):
        assert not self._cols()["content"].nullable

    def test_page_start_column_exists(self):
        assert "page_start" in self._cols()

    def test_page_start_is_nullable(self):
        assert self._cols()["page_start"].nullable

    def test_page_start_is_integer_type(self):
        assert isinstance(self._cols()["page_start"].type, Integer)

    def test_page_end_column_exists(self):
        assert "page_end" in self._cols()

    def test_page_end_is_nullable(self):
        assert self._cols()["page_end"].nullable

    def test_element_types_column_exists(self):
        assert "element_types" in self._cols()

    def test_element_types_is_nullable(self):
        assert self._cols()["element_types"].nullable

    def test_chunk_index_column_exists(self):
        assert "chunk_index" in self._cols()

    def test_chunk_index_is_not_nullable(self):
        assert not self._cols()["chunk_index"].nullable

    def test_chunk_index_is_integer_type(self):
        assert isinstance(self._cols()["chunk_index"].type, Integer)

    def test_created_at_column_exists(self):
        assert "created_at" in self._cols()

    def test_created_at_is_datetime_type(self):
        assert isinstance(self._cols()["created_at"].type, DateTime)

    def test_created_at_is_not_nullable(self):
        assert not self._cols()["created_at"].nullable

    def test_created_at_has_server_default(self):
        assert self._cols()["created_at"].server_default is not None

    def test_total_column_count(self):
        assert len(list(self._cols())) == 8


# ── IngestionJob ──────────────────────────────────────────────────────────────

class TestIngestionJobTable:
    EXPECTED_COLUMNS = {
        "id", "file_id", "status", "current_stage", "total_stages",
        "error_message", "error_type", "retry_count", "celery_task_id",
        "file_hash", "file_size_bytes", "total_pages",
        "started_at", "completed_at", "created_at", "updated_at",
    }

    def _cols(self):
        return IngestionJob.__table__.columns

    def test_tablename(self):
        assert IngestionJob.__tablename__ == "ingestion_jobs"

    def test_has_all_expected_columns(self):
        actual = set(self._cols().keys())
        assert self.EXPECTED_COLUMNS.issubset(actual)

    def test_total_column_count(self):
        assert len(list(self._cols())) == 16

    def test_id_is_primary_key(self):
        assert self._cols()["id"].primary_key

    def test_id_is_integer_type(self):
        assert isinstance(self._cols()["id"].type, Integer)

    def test_file_id_has_foreign_key(self):
        fks = list(self._cols()["file_id"].foreign_keys)
        assert len(fks) == 1

    def test_file_id_fk_targets_files_data(self):
        fk = list(self._cols()["file_id"].foreign_keys)[0]
        assert "files_data.id" in str(fk.target_fullname)

    def test_file_id_fk_has_cascade_delete(self):
        fk = list(self._cols()["file_id"].foreign_keys)[0]
        assert fk.ondelete == "CASCADE"

    def test_status_is_string_type(self):
        assert isinstance(self._cols()["status"].type, String)

    def test_status_length_is_30(self):
        assert self._cols()["status"].type.length == 30

    def test_status_is_not_nullable(self):
        assert not self._cols()["status"].nullable

    def test_retry_count_is_not_nullable(self):
        assert not self._cols()["retry_count"].nullable

    def test_retry_count_is_integer_type(self):
        assert isinstance(self._cols()["retry_count"].type, Integer)

    def test_total_stages_is_not_nullable(self):
        assert not self._cols()["total_stages"].nullable

    def test_current_stage_is_nullable(self):
        assert self._cols()["current_stage"].nullable

    def test_error_message_is_nullable(self):
        assert self._cols()["error_message"].nullable

    def test_error_message_is_text_type(self):
        assert isinstance(self._cols()["error_message"].type, Text)

    def test_error_type_is_nullable(self):
        assert self._cols()["error_type"].nullable

    def test_celery_task_id_is_nullable(self):
        assert self._cols()["celery_task_id"].nullable

    def test_file_hash_is_nullable(self):
        assert self._cols()["file_hash"].nullable

    def test_file_size_bytes_is_nullable(self):
        assert self._cols()["file_size_bytes"].nullable

    def test_total_pages_is_nullable(self):
        assert self._cols()["total_pages"].nullable

    def test_started_at_is_nullable(self):
        assert self._cols()["started_at"].nullable

    def test_completed_at_is_nullable(self):
        assert self._cols()["completed_at"].nullable

    def test_created_at_is_not_nullable(self):
        assert not self._cols()["created_at"].nullable

    def test_created_at_has_server_default(self):
        assert self._cols()["created_at"].server_default is not None

    def test_updated_at_is_not_nullable(self):
        assert not self._cols()["updated_at"].nullable

    def test_updated_at_has_server_default(self):
        assert self._cols()["updated_at"].server_default is not None


# ── IngestionJob status constants ─────────────────────────────────────────────

class TestIngestionJobStatusConstants:
    def test_status_queued(self):
        assert IngestionJob.STATUS_QUEUED == "QUEUED"

    def test_status_stage_1(self):
        assert IngestionJob.STATUS_STAGE_1 == "STAGE_1"

    def test_status_stage_2(self):
        assert IngestionJob.STATUS_STAGE_2 == "STAGE_2"

    def test_status_stage_3(self):
        assert IngestionJob.STATUS_STAGE_3 == "STAGE_3"

    def test_status_stage_4(self):
        assert IngestionJob.STATUS_STAGE_4 == "STAGE_4"

    def test_status_stage_5(self):
        assert IngestionJob.STATUS_STAGE_5 == "STAGE_5"

    def test_status_stage_6(self):
        assert IngestionJob.STATUS_STAGE_6 == "STAGE_6"

    def test_status_complete(self):
        assert IngestionJob.STATUS_COMPLETE == "COMPLETE"

    def test_status_failed_permanent(self):
        assert IngestionJob.STATUS_FAILED_PERMANENT == "FAILED_PERMANENT"

    def test_status_failed_retryable(self):
        assert IngestionJob.STATUS_FAILED_RETRYABLE == "FAILED_RETRYABLE"

    def test_valid_statuses_is_frozenset(self):
        assert isinstance(IngestionJob.VALID_STATUSES, frozenset)

    def test_valid_statuses_count_is_10(self):
        assert len(IngestionJob.VALID_STATUSES) == 10

    def test_valid_statuses_contains_all_constants(self):
        expected = {
            "QUEUED", "STAGE_1", "STAGE_2", "STAGE_3", "STAGE_4",
            "STAGE_5", "STAGE_6", "COMPLETE", "FAILED_PERMANENT", "FAILED_RETRYABLE",
        }
        assert IngestionJob.VALID_STATUSES == expected

    def test_valid_statuses_does_not_contain_unknown(self):
        assert "UNKNOWN" not in IngestionJob.VALID_STATUSES

    def test_terminal_statuses_are_in_valid_statuses(self):
        terminals = {"COMPLETE", "FAILED_PERMANENT", "FAILED_RETRYABLE"}
        assert terminals.issubset(IngestionJob.VALID_STATUSES)

    def test_stage_statuses_are_in_valid_statuses(self):
        stages = {"STAGE_1", "STAGE_2", "STAGE_3", "STAGE_4", "STAGE_5", "STAGE_6"}
        assert stages.issubset(IngestionJob.VALID_STATUSES)


# ── FileRecord new ingestion columns ─────────────────────────────────────────

class TestFileRecordIngestionColumns:
    def _cols(self):
        return FileRecord.__table__.columns

    def test_file_hash_column_exists(self):
        assert "file_hash" in self._cols()

    def test_file_hash_is_string_type(self):
        assert isinstance(self._cols()["file_hash"].type, String)

    def test_file_hash_length_is_64(self):
        assert self._cols()["file_hash"].type.length == 64

    def test_file_hash_is_nullable(self):
        assert self._cols()["file_hash"].nullable

    def test_document_version_column_exists(self):
        assert "document_version" in self._cols()

    def test_document_version_is_integer_type(self):
        assert isinstance(self._cols()["document_version"].type, Integer)

    def test_document_version_is_nullable(self):
        assert self._cols()["document_version"].nullable

    def test_ingestion_status_column_exists(self):
        assert "ingestion_status" in self._cols()

    def test_ingestion_status_is_string_type(self):
        assert isinstance(self._cols()["ingestion_status"].type, String)

    def test_ingestion_status_length_is_30(self):
        assert self._cols()["ingestion_status"].type.length == 30

    def test_ingestion_status_is_nullable(self):
        assert self._cols()["ingestion_status"].nullable

    def test_language_column_exists(self):
        assert "language" in self._cols()

    def test_language_is_string_type(self):
        assert isinstance(self._cols()["language"].type, String)

    def test_language_length_is_10(self):
        assert self._cols()["language"].type.length == 10

    def test_language_is_nullable(self):
        assert self._cols()["language"].nullable

    def test_total_pages_column_exists(self):
        assert "total_pages" in self._cols()

    def test_total_pages_is_integer_type(self):
        assert isinstance(self._cols()["total_pages"].type, Integer)

    def test_total_pages_is_nullable(self):
        assert self._cols()["total_pages"].nullable


# ── Cross-model consistency ───────────────────────────────────────────────────

class TestCrossModelConsistency:
    def test_document_parent_and_ingestion_job_target_same_table(self):
        dp_fk = list(DocumentParent.__table__.columns["file_id"].foreign_keys)[0]
        ij_fk = list(IngestionJob.__table__.columns["file_id"].foreign_keys)[0]
        assert dp_fk.target_fullname == ij_fk.target_fullname

    def test_document_parent_pk_length_matches_job_file_hash_length(self):
        dp_pk_len = DocumentParent.__table__.columns["id"].type.length
        ij_hash_len = IngestionJob.__table__.columns["file_hash"].type.length
        assert dp_pk_len == ij_hash_len == 64

    def test_file_record_file_hash_length_matches_document_parent_pk(self):
        fr_hash_len = FileRecord.__table__.columns["file_hash"].type.length
        dp_pk_len = DocumentParent.__table__.columns["id"].type.length
        assert fr_hash_len == dp_pk_len
