"""add_drive_backup_and_retry_fields

Revision ID: 8f2c3b4a5d6e
Revises: 53e273e6cd12
Create Date: 2026-11-10 14:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f2c3b4a5d6e'
down_revision: Union[str, Sequence[str], None] = '53e273e6cd12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to add Drive backup data and automatic retry telemetry."""
    op.add_column('images', sa.Column('drive_retry_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('images', sa.Column('drive_next_retry_at', sa.DateTime(), nullable=True))
    op.create_index('ix_images_drive_next_retry_at', 'images', ['drive_next_retry_at'], unique=False)
    op.add_column('images', sa.Column('drive_last_error', sa.Text(), nullable=True))
    op.add_column('images', sa.Column('drive_backup_data', sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    """Downgrade schema to remove Drive backup and retry fields."""
    op.drop_column('images', 'drive_backup_data')
    op.drop_column('images', 'drive_last_error')
    op.drop_index('ix_images_drive_next_retry_at', table_name='images')
    op.drop_column('images', 'drive_next_retry_at')
    op.drop_column('images', 'drive_retry_count')
