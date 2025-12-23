"""add weather_config table

Revision ID: d1a2b3c4d5e6
Revises: ca6f816d92d0
Create Date: 2025-12-16 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd1a2b3c4d5e6'
down_revision: Union[str, None] = 'ca6f816d92d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'weather_config',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('providers', postgresql.JSONB(), nullable=False, default=[]),
        sa.Column('fallback_data', postgresql.JSONB(), nullable=True),
        sa.Column('cache_minutes', sa.Integer(), nullable=False, default=30),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, default=10),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('weather_config')
