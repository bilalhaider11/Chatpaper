"""drop citations column from conversation

Revision ID: 0014_drop_citations_from_conversation
Revises: 0013_add_citations_to_conversation
Create Date: 2026-06-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0014_drop_citations_from_conversation'
down_revision: Union[str, None] = '0013_add_citations_to_conversation'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('conversation', 'citations')


def downgrade() -> None:
    op.add_column(
        'conversation',
        sa.Column('citations', sa.JSON(), nullable=True),
    )
