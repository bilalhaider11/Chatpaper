"""
Integration tests that verify the Alembic-migrated schema.
Skipped automatically if PostgreSQL is unreachable.
Run with: pytest -m integration
"""

import os

import pytest
from sqlalchemy import inspect as sa_inspect, text

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def db_engine():
    from sqlalchemy import create_engine
    from core.config import settings

    try:
        engine = create_engine(settings.database, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        yield engine
        engine.dispose()
    except Exception as exc:
        pytest.skip(f"PostgreSQL not reachable — skipping integration tests: {exc}")


@pytest.fixture(scope="module")
def alembic_cfg():
    from alembic.config import Config

    ini_path = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
    cfg = Config(ini_path)
    return cfg



class TestTablesExist:
    def test_document_parents_table_exists(self, db_engine):
        assert "document_parents" in sa_inspect(db_engine).get_table_names()

    def test_ingestion_jobs_table_exists(self, db_engine):
        assert "ingestion_jobs" in sa_inspect(db_engine).get_table_names()

    def test_files_data_table_exists(self, db_engine):
        assert "files_data" in sa_inspect(db_engine).get_table_names()



class TestFilesDataNewColumns:
    def _col_names(self, db_engine):
        return {c["name"] for c in sa_inspect(db_engine).get_columns("files_data")}

    def test_file_hash_column_exists(self, db_engine):
        assert "file_hash" in self._col_names(db_engine)

    def test_document_version_column_exists(self, db_engine):
        assert "document_version" in self._col_names(db_engine)

    def test_ingestion_status_column_exists(self, db_engine):
        assert "ingestion_status" in self._col_names(db_engine)

    def test_language_column_exists(self, db_engine):
        assert "language" in self._col_names(db_engine)

    def test_total_pages_column_exists(self, db_engine):
        assert "total_pages" in self._col_names(db_engine)

    def test_user_id_file_hash_index_exists(self, db_engine):
        indexes = {i["name"] for i in sa_inspect(db_engine).get_indexes("files_data")}
        assert "ix_files_data_user_id_file_hash" in indexes



class TestDocumentParentsStructure:
    def _col_names(self, db_engine):
        return {c["name"] for c in sa_inspect(db_engine).get_columns("document_parents")}

    def test_id_column_exists(self, db_engine):
        assert "id" in self._col_names(db_engine)

    def test_file_id_column_exists(self, db_engine):
        assert "file_id" in self._col_names(db_engine)

    def test_content_column_exists(self, db_engine):
        assert "content" in self._col_names(db_engine)

    def test_chunk_index_column_exists(self, db_engine):
        assert "chunk_index" in self._col_names(db_engine)

    def test_element_types_column_exists(self, db_engine):
        assert "element_types" in self._col_names(db_engine)

    def test_pk_is_id(self, db_engine):
        pk = sa_inspect(db_engine).get_pk_constraint("document_parents")
        assert "id" in pk["constrained_columns"]

    def test_file_id_fk_references_files_data(self, db_engine):
        fks = sa_inspect(db_engine).get_foreign_keys("document_parents")
        fk_cols = [fk["constrained_columns"][0] for fk in fks]
        assert "file_id" in fk_cols

    def test_file_id_index_exists(self, db_engine):
        indexes = {i["name"] for i in sa_inspect(db_engine).get_indexes("document_parents")}
        assert "ix_document_parents_file_id" in indexes

    def test_chunk_index_index_exists(self, db_engine):
        indexes = {i["name"] for i in sa_inspect(db_engine).get_indexes("document_parents")}
        assert "ix_document_parents_chunk_index" in indexes



class TestIngestionJobsStructure:
    EXPECTED_COLUMNS = {
        "id", "file_id", "status", "current_stage", "total_stages",
        "error_message", "error_type", "retry_count", "celery_task_id",
        "file_hash", "file_size_bytes", "total_pages",
        "started_at", "completed_at", "created_at", "updated_at",
    }

    def _col_names(self, db_engine):
        return {c["name"] for c in sa_inspect(db_engine).get_columns("ingestion_jobs")}

    def test_all_expected_columns_exist(self, db_engine):
        actual = self._col_names(db_engine)
        assert self.EXPECTED_COLUMNS.issubset(actual)

    def test_pk_is_id(self, db_engine):
        pk = sa_inspect(db_engine).get_pk_constraint("ingestion_jobs")
        assert "id" in pk["constrained_columns"]

    def test_file_id_fk_references_files_data(self, db_engine):
        fks = sa_inspect(db_engine).get_foreign_keys("ingestion_jobs")
        fk_cols = [fk["constrained_columns"][0] for fk in fks]
        assert "file_id" in fk_cols

    def test_file_id_index_exists(self, db_engine):
        indexes = {i["name"] for i in sa_inspect(db_engine).get_indexes("ingestion_jobs")}
        assert "ix_ingestion_jobs_file_id" in indexes

    def test_status_index_exists(self, db_engine):
        indexes = {i["name"] for i in sa_inspect(db_engine).get_indexes("ingestion_jobs")}
        assert "ix_ingestion_jobs_status" in indexes

    def test_celery_task_id_index_exists(self, db_engine):
        indexes = {i["name"] for i in sa_inspect(db_engine).get_indexes("ingestion_jobs")}
        assert "ix_ingestion_jobs_celery_task_id" in indexes



class TestAlembicHeadConsistency:
    def test_database_is_at_latest_revision(self, db_engine, alembic_cfg):
        from alembic.runtime.migration import MigrationContext

        with db_engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            current_heads = ctx.get_current_heads()

        assert "0006_create_ingestion_tables" in current_heads
