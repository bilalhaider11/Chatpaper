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
revision: str = '17f430d66c73'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "files_data",

        sa.Column("id", sa.Integer(), primary_key=True, index=True),

        # Foreign key to users table
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),

        # File information
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_url", sa.Text(), nullable=False),
        sa.Column("file_type", sa.String(length=100), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),

        # Optional metadata
        sa.Column("description", sa.Text(), nullable=True),

        # Timestamps
        sa.Column(
            "uploaded_at",
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
    op.drop_table("files_data")
    
    