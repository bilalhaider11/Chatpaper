"""add name column to users

Revision ID: 0015_add_name_to_users
Revises: 0014_drop_citations_from_conversation
Create Date: 2026-06-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_add_name_to_users"
down_revision: Union[str, None] = "0014_drop_citations_from_conversation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("name", sa.String(), nullable=True))
    op.execute("UPDATE users SET name = 'user' WHERE name IS NULL")
    op.alter_column("users", "name", nullable=False)


def downgrade() -> None:
    op.drop_column("users", "name")
