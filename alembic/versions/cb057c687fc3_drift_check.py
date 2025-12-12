"""drift check

Revision ID: cb057c687fc3
Revises: bb208a37ee90
Create Date: 2025-12-12 21:09:54.938263

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cb057c687fc3'
down_revision: Union[str, Sequence[str], None] = 'bb208a37ee90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_weather_cache_data_gin",
        "weather_cache",
        ["weather_data"],
        unique=False,
        postgresql_using="gin",
        if_not_exists=True,
    )

def downgrade() -> None:
    op.drop_index(
        "idx_weather_cache_data_gin",
        table_name="weather_cache",
        if_exists=True,
    )
