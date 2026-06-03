"""add conversation_type and file_id to conversationlist

Revision ID: 0010_add_conversation_type_and_file_id
Revises: 0009_add_fts_index
Create Date: 2026-05-25

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_add_conversation_type_and_file_id"
down_revision: Union[str, None] = "0009_add_fts_index"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversationlist",
        sa.Column("conversation_type", sa.String(20), nullable=False, server_default="global"),
    )
    op.add_column(
        "conversationlist",
        sa.Column("file_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_conversationlist_file_id",
        "conversationlist",
        "files_data",
        ["file_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_conversationlist_file_id", "conversationlist", type_="foreignkey")
    op.drop_column("conversationlist", "file_id")
    op.drop_column("conversationlist", "conversation_type")
