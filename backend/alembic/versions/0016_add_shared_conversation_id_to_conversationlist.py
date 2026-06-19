"""create combined_shared_conversation_import table

Revision ID: 0017_add_shared_conversation_id_to_conversationlist
Revises: 0016_add_col_in_convlist_tracking_sharedchats
Create Date: 2026-06-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_add_shared_conversation_id_to_conversationlist"
down_revision: Union[str, None] = "0015_add_name_to_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "combined_shared_conversation_import",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "shared_chat_id",
            sa.Integer(),
            sa.ForeignKey("conversationlist.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("limit", sa.Integer(), nullable=False),
        sa.Column("shared_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_combined_shared_conversation_import_shared_chat_id",
        "combined_shared_conversation_import",
        ["shared_chat_id"],
    )


def downgrade() -> None:
    
    op.drop_table("combined_shared_conversation_import")
