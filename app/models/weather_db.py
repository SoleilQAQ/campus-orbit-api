# app/models/weather_db.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import (
    BigInteger,
    Text,
    String,
    TIMESTAMP,
    Integer,
    func,
    Index,
    MetaData
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)

class Base(DeclarativeBase):
    metadata = metadata


class WeatherSnapshot(Base):
    """
    历史天气快照表，对应表 weather_snapshot：
    - 每次从 OpenWeatherMap / 备用接口获取的数据，完整存一份
    """
    __tablename__ = "weather_snapshot"
    __table_args__ = (
        Index("idx_weather_snapshot_city_time", "city", "data_time"),
        Index("idx_weather_snapshot_data_gin", "weather_data", postgresql_using="gin"),
    )
    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    city: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    data_time: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
    )
    weather_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    @staticmethod
    def from_weather_data(
            city: str,
            provider: str,
            data_time_unix: int,
            weather_data: Dict[str, Any],
    ) -> "WeatherSnapshot":
        """
        工具方法：用 WeatherData 里的 dataTime（Unix 秒）构造快照
        """
        return WeatherSnapshot(
            city=city,
            provider=provider,
            data_time=datetime.fromtimestamp(
                data_time_unix,
                tz=timezone.utc,
            ),
            weather_data=weather_data,
        )


class WeatherCache(Base):
    """
    当前天气缓存表，对应表 weather_cache：
    - 每个城市一行
    - 存最近一次有效数据，用于 30 分钟内快速返回
    """
    __tablename__ = "weather_cache"
    __table_args__ = (
        Index("idx_weather_cache_data_gin", "weather_data", postgresql_using="gin"),
    )

    city: Mapped[str] = mapped_column(Text, primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    weather_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    cached_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    expiration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
    )
