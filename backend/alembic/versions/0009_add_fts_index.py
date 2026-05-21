"""add GIN full-text search index on document_parents.content

Revision ID: 0009_add_fts_index
Revises: 0008_add_is_committed_and_embedding_model
Create Date: 2026-05-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_add_fts_index"
down_revision: Union[str, None] = "0008_add_is_committed_and_embedding_model"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS ix_document_parents_content_fts
        ON document_parents
        USING gin(to_tsvector('english', content))
    """))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_document_parents_content_fts"))
