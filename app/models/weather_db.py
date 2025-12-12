# app/models/weather_db.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import BigInteger, Integer, String, Text, TIMESTAMP, func, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy ORM Base"""
    pass


class WeatherSnapshot(Base):
    """
    历史天气快照表：weather_snapshot
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
        return WeatherSnapshot(
            city=city,
            provider=provider,
            data_time=datetime.fromtimestamp(data_time_unix, tz=timezone.utc),
            weather_data=weather_data,
        )


class WeatherCache(Base):
    """
    当前天气缓存表：weather_cache
    - 每个城市一行
    - 存最近一次有效数据，用于 expiration_minutes 内快速返回
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

    # 这里用 server_default，避免 alembic autogenerate 认为 DB 默认值漂移
    expiration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("30"),
    )
