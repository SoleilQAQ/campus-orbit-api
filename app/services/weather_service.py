# app/services/weather_service.py
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.clients.weather_clients import (
    OpenWeatherClient,
    BackupWeatherClient,
)
from app.core.config import settings
from app.models.weather_db import WeatherSnapshot, WeatherCache
from app.models.weather_schemas import (
    WeatherResponse,
    WeatherData,
    LocationInfo,
    CurrentWeather,
    TemperatureInfo,
    WindInfo,
    CacheInfo,
)

logger = logging.getLogger(__name__)


def _convert_openweather_to_weatherdata(
    raw: dict,
    now: datetime,
) -> WeatherData:
    """
    把 OpenWeatherMap 返回的原始 JSON 转成标准 WeatherData
    """
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

    return WeatherData(
        location=location,
        current=current,
        cacheInfo=cache_info,
    )


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

    # ---------- 缓存 & 快照工具方法 ----------

    async def _get_cache(self, city: str) -> WeatherData | None:
        """
        从 weather_cache 表获取有效缓存：
        - city 匹配
        - cached_at + expiration_minutes > now
        """
        now = datetime.now(timezone.utc)

        stmt = (
            select(WeatherCache)
            .where(WeatherCache.city == city)
            .limit(1)
        )
        result = await self.session.execute(stmt)
        row: WeatherCache | None = result.scalar_one_or_none()

        if row is None:
            return None

        expire_at = row.cached_at + timedelta(
            minutes=row.expiration_minutes
        )
        if expire_at <= now:
            # 已过期，当作没命中（后面可以扩展成“stale cache”兜底）
            return None

        # row.weather_data 是用 mode="json" 序列化后的 dict，可以直接解析回 WeatherData
        return WeatherData.model_validate(row.weather_data)

    async def _upsert_cache(
        self,
        city: str,
        provider: str,
        data: WeatherData,
    ) -> None:
        """
        更新 / 插入 weather_cache：
        - 如果 city 已存在，就覆盖 provider / weather_data / 时间等
        """
        now = datetime.now(timezone.utc)
        weather_json = data.model_dump(mode="json")

        stmt = pg_insert(WeatherCache).values(
            city=city,
            provider=provider,
            weather_data=weather_json,
            cached_at=now,
            updated_at=now,
            expiration_minutes=settings.weather_expiration_minutes,
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=[WeatherCache.city],
            set_={
                "provider": stmt.excluded.provider,
                "weather_data": stmt.excluded.weather_data,
                "cached_at": stmt.excluded.cached_at,
                "updated_at": stmt.excluded.updated_at,
                "expiration_minutes": stmt.excluded.expiration_minutes,
            },
        )

        await self.session.execute(stmt)
        await self.session.commit()

    async def _save_snapshot(
        self,
        city: str,
        provider: str,
        data: WeatherData,
    ) -> None:
        """
        写入 weather_snapshot 表：存一份完整历史快照
        """
        weather_json = data.model_dump(mode="json")

        snapshot = WeatherSnapshot.from_weather_data(
            city=city,
            provider=provider,
            data_time_unix=data.current.dataTime,
            weather_data=weather_json,
        )
        self.session.add(snapshot)
        await self.session.commit()

    # ---------- 对外主方法：按城市获取天气 ----------

    async def get_weather_by_city(self, city: str) -> WeatherResponse:
        now = datetime.now(timezone.utc)

        # 0）先查缓存
        try:
            cached = await self._get_cache(city)
        except Exception as e:
            logger.exception("查询天气缓存失败: %s", e)
        else:
            if cached is not None:
                # 命中缓存，直接返回
                cached.cacheInfo.cachedAt = now
                # updatedAt 保持为上次更新时间
                cached.cacheInfo.isValid = True
                cached.cacheInfo.expirationMinutes = (
                    settings.weather_expiration_minutes
                )

                return WeatherResponse(
                    success=True,
                    message="获取天气数据成功（缓存）",
                    source="cache",
                    data=cached,
                    timestamp=now,
                )

        # 1）缓存没命中：调用 OpenWeatherMap
        try:
            raw = await self.openweather_client.get_current_weather(city)
        except httpx.HTTPError as e:
            logger.exception("OpenWeatherMap 调用失败: %s", e)
        else:
            data = _convert_openweather_to_weatherdata(raw, now)

            # 保存快照 & 更新缓存，失败不影响对外返回
            try:
                await self._save_snapshot(
                    city=city,
                    provider="openweathermap",
                    data=data,
                )
            except Exception as e:
                logger.exception("保存 weather_snapshot 失败: %s", e)

            try:
                await self._upsert_cache(
                    city=city,
                    provider="openweathermap",
                    data=data,
                )
            except Exception as e:
                logger.exception("更新 weather_cache 失败: %s", e)

            return WeatherResponse(
                success=True,
                message="获取天气数据成功（OpenWeatherMap）",
                source="api",
                data=data,
                timestamp=now,
            )

        # 2）OpenWeatherMap 挂了：尝试备用接口
        try:
            backup_resp = await self.backup_client.get_weather(city)
            if backup_resp.success and backup_resp.data is not None:
                try:
                    await self._save_snapshot(
                        city=city,
                        provider=backup_resp.source or "backup",
                        data=backup_resp.data,
                    )
                except Exception as e:
                    logger.exception(
                        "保存备用接口 weather_snapshot 失败: %s", e
                    )

                try:
                    await self._upsert_cache(
                        city=city,
                        provider=backup_resp.source or "backup",
                        data=backup_resp.data,
                    )
                except Exception as e:
                    logger.exception(
                        "更新 weather_cache（备用接口）失败: %s", e
                    )

                backup_resp.timestamp = now
                backup_resp.source = backup_resp.source or "backup"
                return backup_resp
        except Exception as e:
            logger.exception("备用天气接口调用失败: %s", e)

        # 3）主接口 + 备用接口都挂了 → 目前直接失败（之后可以加 stale cache 兜底）
        return WeatherResponse(
            success=False,
            message="无法从 OpenWeatherMap 和备用接口获取天气数据",
            source=None,
            data=None,
            timestamp=now,
        )
