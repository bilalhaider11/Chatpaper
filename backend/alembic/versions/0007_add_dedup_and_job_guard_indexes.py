"""add dedup and job guard indexes

Revision ID: 0007_add_dedup_and_job_guard_indexes
Revises: 0006_create_ingestion_tables
Create Date: 2026-05-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_add_dedup_and_job_guard_indexes"
down_revision: Union[str, None] = "0006_create_ingestion_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # same file, different filename — no point embedding it twice
    # partial index so rows without a hash yet don't conflict
    op.create_index(
        "ix_files_data_user_file_hash",
        "files_data",
        ["user_id", "file_hash"],
        unique=True,
        postgresql_where=sa.text("file_hash IS NOT NULL"),
    )

    # one active job per file; terminal statuses excluded so failed files can be retried
    op.execute(
        """
        CREATE UNIQUE INDEX ix_ingestion_jobs_one_active_per_file
        ON ingestion_jobs (file_id)
        WHERE status NOT IN ('COMPLETE', 'FAILED_PERMANENT')
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_ingestion_jobs_one_active_per_file")
    op.drop_index("ix_files_data_user_file_hash", table_name="files_data")
