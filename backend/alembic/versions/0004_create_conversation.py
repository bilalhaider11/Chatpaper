"""create conversation table

Revision ID: 0004_create_conversation
Revises: 0003_create_conversation_list
Create Date: 2026-05-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0004_create_conversation'
down_revision: Union[str, None] = '0003_create_conversation_list'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'conversation',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('chat_id', sa.Integer(), sa.ForeignKey('conversationlist.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_type', sa.String(length=50), nullable=False),
        sa.Column('statement', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('conversation')
