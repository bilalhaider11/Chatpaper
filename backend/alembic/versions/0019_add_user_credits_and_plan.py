"""add credits and plan columns to users

Revision ID: 0019_add_user_credits_and_plan
Revises: 0018_create_subscription_table
Create Date: 2026-06-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019_add_user_credits_and_plan"
down_revision: Union[str, None] = "0018_create_subscription_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("credits", sa.Integer(), nullable=True),
    )

def downgrade() -> None:
    op.drop_column("users", "credits")
