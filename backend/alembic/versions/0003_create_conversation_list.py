"""create conversationlist table

Revision ID: 0003_create_conversation_list
Revises: 0002_create_files_data
Create Date: 2026-05-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0003_create_conversation_list'
down_revision: Union[str, None] = '0002_create_files_data'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'conversationlist',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('conversation_title', sa.String(150), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('is_Active', sa.Boolean(), default=True, nullable=False),
    )


def downgrade() -> None:
    op.drop_table('conversationlist')
