"""add citations column to conversation

Revision ID: 0013_add_citations_to_conversation
Revises: 0012_add_fk_performance_indexes
Create Date: 2026-06-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0013_add_citations_to_conversation'
down_revision: Union[str, None] = '0012_add_fk_performance_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'conversation',
        sa.Column('citations', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('conversation', 'citations')
