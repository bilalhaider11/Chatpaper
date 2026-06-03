"""add FK performance indexes

Revision ID: 0012_add_fk_performance_indexes
Revises: 0011_add_auth_provider_nullable_password
Create Date: 2026-06-02

"""

from typing import Sequence, Union

from alembic import op

revision: str = "0012_add_fk_performance_indexes"
down_revision: Union[str, None] = "0011_add_auth_provider_nullable_password"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # conversation.chat_id — queried on every GET /get-conversation/{id}
    op.create_index("ix_conversation_chat_id", "conversation", ["chat_id"])
    # conversationlist.user_id — queried on every conversation list fetch and ownership check
    op.create_index("ix_conversationlist_user_id", "conversationlist", ["user_id"])
    # conversationlist.file_id — queried during upload duplicate detection and per_file lookups
    op.create_index("ix_conversationlist_file_id", "conversationlist", ["file_id"])
    # files_data.user_id — queried on every file list, quota check, and ownership check
    # (the existing composite index on (user_id, file_hash) does not cover standalone user_id scans)
    op.create_index("ix_files_data_user_id", "files_data", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_files_data_user_id", table_name="files_data")
    op.drop_index("ix_conversationlist_file_id", table_name="conversationlist")
    op.drop_index("ix_conversationlist_user_id", table_name="conversationlist")
    op.drop_index("ix_conversation_chat_id", table_name="conversation")
