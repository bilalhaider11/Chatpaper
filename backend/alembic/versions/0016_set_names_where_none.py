"""make user name nullable"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "0016_set_names_where_none"
down_revision = "0015_add_name_to_users"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""
        UPDATE users
        SET name = 'user'
        WHERE name IS NULL;
    """)


def downgrade():
    # optional rollback (usually NOT recommended for data fixes)
    op.execute("""
        UPDATE users
        SET name = NULL
        WHERE name = 'user';
    """)