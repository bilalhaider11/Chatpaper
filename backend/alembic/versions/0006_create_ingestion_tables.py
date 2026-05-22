"""create ingestion tables

Revision ID: 0006_create_ingestion_tables
Revises: 0005_add_file_fields_for_ingestion
Create Date: 2026-05-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = '0006_create_ingestion_tables'
down_revision: Union[str, None] = '0005_add_file_fields_for_ingestion'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'document_parents',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('file_id', sa.Integer(), sa.ForeignKey('files_data.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('page_start', sa.Integer(), nullable=True),
        sa.Column('page_end', sa.Integer(), nullable=True),
        sa.Column('element_types', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_document_parents_file_id', 'document_parents', ['file_id'])
    op.create_index('ix_document_parents_chunk_index', 'document_parents', ['chunk_index'])

    op.create_table(
        'ingestion_jobs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('file_id', sa.Integer(), sa.ForeignKey('files_data.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('current_stage', sa.Integer(), nullable=True),
        sa.Column('total_stages', sa.Integer(), nullable=False, server_default='6'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_type', sa.String(100), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('celery_task_id', sa.String(255), nullable=True),
        sa.Column('file_hash', sa.String(64), nullable=True),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('total_pages', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_ingestion_jobs_file_id', 'ingestion_jobs', ['file_id'])
    op.create_index('ix_ingestion_jobs_status', 'ingestion_jobs', ['status'])
    op.create_index('ix_ingestion_jobs_celery_task_id', 'ingestion_jobs', ['celery_task_id'])


def downgrade() -> None:
    op.drop_index('ix_ingestion_jobs_celery_task_id', table_name='ingestion_jobs')
    op.drop_index('ix_ingestion_jobs_status', table_name='ingestion_jobs')
    op.drop_index('ix_ingestion_jobs_file_id', table_name='ingestion_jobs')
    op.drop_table('ingestion_jobs')

    op.drop_index('ix_document_parents_chunk_index', table_name='document_parents')
    op.drop_index('ix_document_parents_file_id', table_name='document_parents')
    op.drop_table('document_parents')
