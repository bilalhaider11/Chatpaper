"""add cancel_subscription column to subscription 

Revision ID: 0021_track_cancel_subscription
Revises: 0020_subscription_plan_change_fields
Create Date: 2026-06-30

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021_track_cancel_subscription"
down_revision: Union[str, None] = "0020_subscription_plan_change_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "subscription",
        sa.Column("cancel_subscription", sa.Boolean(),server_default=sa.false()),
    )

def downgrade() -> None:
    op.drop_column("subscription", "cancel_subscription")
