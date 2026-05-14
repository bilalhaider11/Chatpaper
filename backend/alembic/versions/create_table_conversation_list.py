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
revision: str = 'conversationlist'
down_revision: Union[str, None] = '17f430d66c73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversationlist",

        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        
        sa.Column("conversation_title", sa.String(150),nullable=False),

        # Foreign key to users table
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),

        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        
        sa.Column(
            "is_Active",
            sa.Boolean,
            default=True,
            nullable=False
        )

    )


def downgrade() -> None:
    op.drop_table("conversationlist")
    
    