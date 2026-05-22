"""add is_committed and embedding_model columns

Revision ID: 0008_add_is_committed_and_embedding_model
Revises: 0007_add_dedup_and_job_guard_indexes
Create Date: 2026-05-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_add_is_committed_and_embedding_model"
down_revision: Union[str, None] = "0007_add_dedup_and_job_guard_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # set True once chroma write succeeds — retries skip already-committed parents
    op.add_column(
        "document_parents",
        sa.Column("is_committed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # needed to identify which docs require re-embedding after a model upgrade
    op.add_column(
        "document_parents",
        sa.Column("embedding_model", sa.String(100), nullable=True),
    )
    op.add_column(
        "files_data",
        sa.Column("embedding_model", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("files_data", "embedding_model")
    op.drop_column("document_parents", "embedding_model")
    op.drop_column("document_parents", "is_committed")
