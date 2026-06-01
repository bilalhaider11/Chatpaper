"""add auth_provider column and make password nullable

Revision ID: 0011_add_auth_provider_nullable_password
Revises: 0010_add_conversation_type_and_file_id
Create Date: 2026-06-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_add_auth_provider_nullable_password"
down_revision: Union[str, None] = "0010_add_conversation_type_and_file_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "auth_provider",
            sa.String(),
            nullable=False,
            server_default="password",
        ),
    )
    op.alter_column("users", "password", nullable=True)


def downgrade() -> None:
    # Restore NOT NULL — rows with NULL password (OAuth users) must be handled before downgrading
    op.alter_column("users", "password", nullable=False)
    op.drop_column("users", "auth_provider")
