# app/models/weather_schemas.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class LocationInfo(BaseModel):
    cityName: str
    countryCode: str
    latitude: float
    longitude: float
    timezone: int


class TemperatureInfo(BaseModel):
    current: float
    min: float
    max: float
    feels_like: float


class WindInfo(BaseModel):
    speed: float
    degree: int
    gust: Optional[float] = None


class PrecipitationInfo(BaseModel):
    """降水信息（雨/雪）"""
    h1: Optional[float] = None  # 过去1小时降水量 (mm)
    h3: Optional[float] = None  # 过去3小时降水量 (mm)


class CurrentWeather(BaseModel):
    main: str
    description: str
    icon: str
    iconUrl: str
    temperature: TemperatureInfo
    pressure: int
    humidity: int
    visibility: int
    wind: WindInfo
    clouds: int
    sunrise: int
    sunset: int
    dataTime: int
    # 可选的降水信息
    rain: Optional[PrecipitationInfo] = None  # 雨量
    snow: Optional[PrecipitationInfo] = None  # 雪量
    seaLevel: Optional[int] = None  # 海平面气压 (hPa)
    groundLevel: Optional[int] = None  # 地面气压 (hPa)


class CacheInfo(BaseModel):
    cachedAt: datetime
    updatedAt: datetime
    isValid: bool
    expirationMinutes: int


class WeatherData(BaseModel):
    location: LocationInfo
    current: CurrentWeather
    cacheInfo: CacheInfo


class WeatherResponse(BaseModel):
    success: bool
    message: str
    source: Optional[str] = None
    data: Optional[WeatherData] = None
    timestamp: datetime


# -------- 新增：历史快照 --------

class WeatherSnapshotItem(BaseModel):
    id: int
    city: str
    provider: str
    dataTime: datetime
    createdAt: datetime
    data: "WeatherData"


class WeatherHistoryResponse(BaseModel):
    success: bool
    message: str
    city: str
    count: int
    items: List[WeatherSnapshotItem]
    timestamp: datetime

# WeatherSnapshotItem.model_rebuild()