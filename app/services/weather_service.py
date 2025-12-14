# app/services/weather_service.py
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.weather_client import BackupWeatherClient, OpenWeatherClient
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.weather_models import WeatherCache, WeatherSnapshot
from app.schemas.weather_schemas import (
    CacheInfo,
    CurrentWeather,
    LocationInfo,
    TemperatureInfo,
    WeatherData,
    WeatherHistoryResponse,
    WeatherResponse,
    WeatherSnapshotItem,
    WindInfo,
)

logger = logging.getLogger(__name__)


def _convert_openweather_to_weatherdata(raw: dict, now: datetime) -> WeatherData:
    coord = raw["coord"]
    weather0 = raw["weather"][0]
    main = raw["main"]
    wind = raw.get("wind", {})
    clouds = raw.get("clouds", {})
    sys = raw.get("sys", {})
    dt = raw["dt"]
    timezone_offset = raw.get("timezone", 0)

    icon = weather0["icon"]
    icon_url = f"https://openweathermap.org/img/wn/{icon}@2x.png"

    location = LocationInfo(
        cityName=raw.get("name", ""),
        countryCode=sys.get("country", ""),
        latitude=coord["lat"],
        longitude=coord["lon"],
        timezone=timezone_offset,
    )

    temperature = TemperatureInfo(
        current=main["temp"],
        min=main.get("temp_min", main["temp"]),
        max=main.get("temp_max", main["temp"]),
        feels_like=main["feels_like"],
    )

    wind_info = WindInfo(
        speed=wind.get("speed", 0.0),
        degree=wind.get("deg", 0),
        gust=wind.get("gust"),
    )

    current = CurrentWeather(
        main=weather0["main"],
        description=weather0["description"],
        icon=icon,
        iconUrl=icon_url,
        temperature=temperature,
        pressure=main["pressure"],
        humidity=main["humidity"],
        visibility=raw.get("visibility", 0),
        wind=wind_info,
        clouds=clouds.get("all", 0),
        sunrise=sys.get("sunrise", 0),
        sunset=sys.get("sunset", 0),
        dataTime=dt,
    )

    cache_info = CacheInfo(
        cachedAt=now,
        updatedAt=now,
        isValid=True,
        expirationMinutes=settings.weather_expiration_minutes,
    )

    return WeatherData(location=location, current=current, cacheInfo=cache_info)


class WeatherService:
    def __init__(
        self,
        openweather_client: OpenWeatherClient,
        backup_client: BackupWeatherClient,
        session: AsyncSession,
    ) -> None:
        self.openweather_client = openweather_client
        self.backup_client = backup_client
        self.session = session

    @staticmethod
    def _normalize_city(city: str) -> str:
        return city.strip()

    async def _get_cache(self, city: str) -> WeatherData | None:
        now = datetime.now(timezone.utc)
        stmt = select(WeatherCache).where(WeatherCache.city == city).limit(1)

        try:
            row = (await self.session.execute(stmt)).scalar_one_or_none()
        except (DBAPIError, SQLAlchemyError) as e:
            logger.exception("查询天气缓存失败，视为无缓存: %s", e)
            # 关键：把 session 从 failed 状态拉回来
            try:
                await self.session.rollback()
            except Exception:
                logger.warning("查询缓存失败后 rollback 也失败，忽略", exc_info=True)
            return None

        if row is None:
            return None

        expire_at = row.cached_at + timedelta(minutes=row.expiration_minutes)
        if expire_at <= now:
            return None

        data = WeatherData.model_validate(row.weather_data)
        data.cacheInfo.cachedAt = row.cached_at
        data.cacheInfo.updatedAt = row.updated_at
        data.cacheInfo.isValid = True
        data.cacheInfo.expirationMinutes = row.expiration_minutes
        return data

    async def _persist_snapshot_and_cache(
            self, city: str, provider: str, data: WeatherData
    ) -> None:
        """
        使用独立的短生命周期 Session，将天气快照 + 缓存写入数据库。

        这样可以避免与当前请求的 AsyncSession 之间产生并发冲突
        （asyncpg: "another operation is in progress"）。
        """
        now = datetime.now(timezone.utc)
        weather_json = data.model_dump(mode="json")

        snapshot = WeatherSnapshot.from_weather_data(
            city=city,
            provider=provider,
            data_time_unix=data.current.dataTime,
            weather_data=weather_json,
        )

        upsert_stmt = (
            pg_insert(WeatherCache)
            .values(
                city=city,
                provider=provider,
                weather_data=weather_json,
                cached_at=now,
                updated_at=now,
                expiration_minutes=settings.weather_expiration_minutes,
            )
            .on_conflict_do_update(
                index_elements=[WeatherCache.city],
                set_={
                    "provider": provider,
                    "weather_data": weather_json,
                    "cached_at": now,
                    "updated_at": now,
                    "expiration_minutes": settings.weather_expiration_minutes,
                },
            )
        )

        #  独立 Session，内部事务保证原子性
        async with AsyncSessionLocal() as session:
            try:
                async with session.begin():  # 自动 flush + commit / rollback
                    session.add(snapshot)
                    await session.execute(upsert_stmt)
            except Exception:
                # 这里的异常只影响“是否写入快照/缓存”，不会把外面请求的 session 弄坏
                raise

    async def get_weather_by_city(self, city: str) -> WeatherResponse:
        now = datetime.now(timezone.utc)
        city = self._normalize_city(city)

        # 0）缓存
        try:
            cached = await self._get_cache(city)
            if cached is not None:
                return WeatherResponse(
                    success=True,
                    message="获取天气数据成功（缓存）",
                    source="cache",
                    data=cached,
                    timestamp=now,
                )
        except Exception as e:
            logger.exception("查询天气缓存失败: %s", e)

        # 1）主接口：OpenWeatherMap
        try:
            raw = await self.openweather_client.get_current_weather(city)
            data = _convert_openweather_to_weatherdata(raw, now)

            # 写入（失败不影响对外返回，但我们必须保证 session 不坏）
            try:
                await self._persist_snapshot_and_cache(city, "openweathermap", data)
            except Exception as e:
                logger.exception("写入天气 snapshot/cache 失败: %s", e)

            return WeatherResponse(
                success=True,
                message="获取天气数据成功（OpenWeatherMap）",
                source="api",
                data=data,
                timestamp=now,
            )
        except httpx.HTTPError as e:
            logger.exception("OpenWeatherMap 调用失败: %s", e)

        # 2）备用接口
        try:
            backup_resp = await self.backup_client.get_weather(city)
            if backup_resp.success and backup_resp.data is not None:
                provider = backup_resp.source or "backup"

                try:
                    await self._persist_snapshot_and_cache(city, provider, backup_resp.data)
                except Exception as e:
                    logger.exception("写入备用接口 snapshot/cache 失败: %s", e)

                backup_resp.timestamp = now
                backup_resp.source = provider
                return backup_resp
        except Exception as e:
            logger.exception("备用天气接口调用失败: %s", e)

        return WeatherResponse(
            success=False,
            message="无法从 OpenWeatherMap 和备用接口获取天气数据",
            source=None,
            data=None,
            timestamp=now,
        )

    async def get_weather_history(self, city: str, limit: int = 20) -> WeatherHistoryResponse:
        now = datetime.now(timezone.utc)
        city = self._normalize_city(city)
        limit = max(1, min(limit, 200))

        stmt = (
            select(WeatherSnapshot)
            .where(WeatherSnapshot.city == city)
            .order_by(WeatherSnapshot.data_time.desc())
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        rows = result.scalars().all()

        items: list[WeatherSnapshotItem] = []
        for snap in rows:
            items.append(
                WeatherSnapshotItem(
                    id=snap.id,
                    city=snap.city,
                    provider=snap.provider,
                    dataTime=snap.data_time,
                    createdAt=snap.created_at,
                    data=WeatherData.model_validate(snap.weather_data),
                )
            )

        return WeatherHistoryResponse(
            success=True,
            message="获取历史天气快照成功",
            city=city,
            count=len(items),
            items=items,
            timestamp=now,
        )
