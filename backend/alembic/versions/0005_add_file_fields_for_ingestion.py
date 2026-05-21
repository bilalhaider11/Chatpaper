"""add file fields for ingestion

Revision ID: 0005_add_file_fields_for_ingestion
Revises: 0004_create_conversation
Create Date: 2026-05-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0005_add_file_fields_for_ingestion'
down_revision: Union[str, None] = '0004_create_conversation'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('files_data', sa.Column('file_hash', sa.String(64), nullable=True))
    op.add_column('files_data', sa.Column('document_version', sa.Integer(), nullable=True))
    op.add_column('files_data', sa.Column('ingestion_status', sa.String(30), nullable=True))
    op.add_column('files_data', sa.Column('language', sa.String(10), nullable=True))
    op.add_column('files_data', sa.Column('total_pages', sa.Integer(), nullable=True))
    op.create_index('ix_files_data_user_id_file_hash', 'files_data', ['user_id', 'file_hash'])


def downgrade() -> None:
    op.drop_index('ix_files_data_user_id_file_hash', table_name='files_data')
    op.drop_column('files_data', 'total_pages')
    op.drop_column('files_data', 'language')
    op.drop_column('files_data', 'ingestion_status')
    op.drop_column('files_data', 'document_version')
    op.drop_column('files_data', 'file_hash')
