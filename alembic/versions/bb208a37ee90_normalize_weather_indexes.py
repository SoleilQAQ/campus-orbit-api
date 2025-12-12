"""normalize weather indexes

Revision ID: bb208a37ee90
Revises: 9a85d9c7d23b
Create Date: 2025-12-12 21:09:00.082022

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bb208a37ee90'
down_revision: Union[str, Sequence[str], None] = '9a85d9c7d23b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # weather_cache：删重复的 city 索引（PK 已有索引）
    op.drop_index("idx_weather_cache_city", table_name="weather_cache", if_exists=True)

    # weather_snapshot：删重复的 city_time
    op.drop_index("idx_snapshot_city_time", table_name="weather_snapshot", if_exists=True)
    op.drop_index("idx_weather_snapshot_city_time", table_name="weather_snapshot", if_exists=True)
    op.create_index(
        "idx_weather_snapshot_city_time",
        "weather_snapshot",
        ["city", "data_time"],
        unique=False,
        if_not_exists=True,
    )

    # weather_snapshot：删 jsonb_path_ops 那条，保留默认 GIN
    op.drop_index("idx_snapshot_data_gin", table_name="weather_snapshot", if_exists=True)
    op.drop_index("idx_weather_snapshot_data_gin", table_name="weather_snapshot", if_exists=True)
    op.create_index(
        "idx_weather_snapshot_data_gin",
        "weather_snapshot",
        ["weather_data"],
        unique=False,
        postgresql_using="gin",
        if_not_exists=True,
    )

