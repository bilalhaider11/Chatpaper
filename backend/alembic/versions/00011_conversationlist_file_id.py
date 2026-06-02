"""add file_id to conversationlist

Revision ID: 00011_conversationlist_file_id
Revises: 00010_google_login_track
Create Date: 2026-06-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "00011_conversationlist_file_id"
down_revision: Union[str, None] = "00010_google_login_track"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
    op.drop_column("conversationlist", "file_id")
