"""add is_committed and embedding_model columns

Revision ID: 0009_add_fts_index
Revises: 0010_google_login_track
Create Date: 2026-06-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "00010_google_login_track"
down_revision: Union[str, None] = "0009_add_fts_index"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column("loggedin_by_google", sa.Boolean(), nullable=False, server_default=sa.false()),
    )



def downgrade() -> None:
    
    op.drop_column("users", "loggedin_by_google")
