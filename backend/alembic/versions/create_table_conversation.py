"""create_files_data_table

Revision ID: a1b2c3d4e5f6
Revises: c9ba0998ed62
Create Date: 2026-05-11 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# revision identifiers, used by Alembic.
revision: str = 'conversation'
down_revision: Union[str, None] = 'conversationlist'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        "conversation",

        sa.Column("id", sa.Integer(), primary_key=True, index=True),

        # Foreign key to users table
        sa.Column(
            "chat_id",
            sa.Integer(),
            sa.ForeignKey("conversationlist.id", ondelete="CASCADE"),
            nullable=False,
        ),

        # chat information
        sa.Column("user_type", sa.String(length=50), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),


        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),

    )


def downgrade() -> None:
    op.drop_table("conversation")
    
    