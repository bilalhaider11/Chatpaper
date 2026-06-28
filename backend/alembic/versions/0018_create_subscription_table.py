"""create combined_shared_conversation_import table

Revision ID: 0018_create_subscription_table
Revises: 0017_combined_shared_list
Create Date: 2026-06-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018_create_subscription_table"
down_revision: Union[str, None] = "0017_combined_shared_list"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscription",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stripe_customer_id",sa.Text(),nullable=True),
        sa.Column("subscription_id",sa.Text(),nullable=True),
        sa.Column("product_id",sa.Text(),nullable=True),
        sa.Column("plan",sa.String(20),nullable=False),
        sa.Column("status",sa.Boolean(),default=True,nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

def downgrade() -> None:
    
    op.drop_table("subscription")

