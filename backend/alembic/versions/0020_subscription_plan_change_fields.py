"""add subscription plan-change fields and webhook idempotency

Revision ID: 0020_subscription_plan_change_fields
Revises: 0019_add_user_credits_and_plan
Create Date: 2026-06-24

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020_subscription_plan_change_fields"
down_revision: Union[str, None] = "0019_add_user_credits_and_plan"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "subscription",
        sa.Column("stripe_subscription_item_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "subscription",
        sa.Column("stripe_price_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "subscription",
        sa.Column("current_period_start", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "subscription",
        sa.Column("current_period_end", sa.DateTime(timezone=False), nullable=True),
    )
    op.create_index(
        "ix_subscription_user_id_unique",
        "subscription",
        ["user_id"],
        unique=True,
    )
    op.create_table(
        "stripe_webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(255), nullable=False, unique=True),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=False),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("stripe_webhook_events")
    op.drop_index("ix_subscription_user_id_unique", table_name="subscription")
    op.drop_column("subscription", "current_period_end")
    op.drop_column("subscription", "current_period_start")
    op.drop_column("subscription", "stripe_price_id")
    op.drop_column("subscription", "stripe_subscription_item_id")
