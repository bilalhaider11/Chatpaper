"""add shared_conversation_id to conversationlist

Revision ID: 0018_combined_shared_list
Revises: 0017_add_shared_conversation_id_to_conversationlist
Create Date: 2026-06-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
revision: str = '0017_combined_shared_list'
down_revision: Union[str, None] = '0016_add_shared_conversation_id_to_conversationlist'

branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversationlist",
        sa.Column(
            "shared_conversation_id",
            sa.Integer(),
            sa.ForeignKey("combined_shared_conversation_import.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
   
    op.drop_column("conversationlist", "shared_conversation_id")
