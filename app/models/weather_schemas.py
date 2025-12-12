# app/models/weather_schemas.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

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
