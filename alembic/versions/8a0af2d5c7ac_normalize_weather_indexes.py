"""normalize weather indexes

Revision ID: 8a0af2d5c7ac
Revises: cb057c687fc3
Create Date: 2025-12-12 21:14:44.208436

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8a0af2d5c7ac'
down_revision: Union[str, Sequence[str], None] = 'cb057c687fc3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.drop_index("idx_weather_cache_city", table_name="weather_cache", if_exists=True)

    op.drop_index("idx_snapshot_city_time", table_name="weather_snapshot", if_exists=True)

    # 二选一：建议先删掉 jsonb_path_ops 那条，保留默认 GIN
    op.drop_index("idx_snapshot_data_gin", table_name="weather_snapshot", if_exists=True)

    # 确保“唯一真相”存在（可加 if_not_exists）
    op.create_index(
        "idx_weather_snapshot_city_time",
        "weather_snapshot",
        ["city", "data_time"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "idx_weather_snapshot_data_gin",
        "weather_snapshot",
        ["weather_data"],
        unique=False,
        postgresql_using="gin",
        if_not_exists=True,
    )



def downgrade() -> None:
    """Downgrade schema."""
    pass
