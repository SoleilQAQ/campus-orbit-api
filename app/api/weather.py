# app/api/weather.py
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.weather_clients import BackupWeatherClient, OpenWeatherClient
from app.db.session import get_session
from app.schemas.weather_schemas import WeatherHistoryResponse, WeatherResponse
from app.services.weather_service import WeatherService

router = APIRouter(prefix="/api", tags=["weather"])


@router.get("/weather", response_model=WeatherResponse)
async def get_weather(
    request: Request,
    city: str = Query(..., description="城市名，例如 beijing"),
    session: AsyncSession = Depends(get_session),
) -> WeatherResponse:
    http_client = request.app.state.http_client
    service = WeatherService(
        openweather_client=OpenWeatherClient(http_client),
        backup_client=BackupWeatherClient(http_client),
        session=session,
    )
    return await service.get_weather_by_city(city)


@router.get("/weather/history", response_model=WeatherHistoryResponse)
async def get_weather_history(
    request: Request,
    city: str = Query(..., description="城市名，例如 beijing"),
    limit: int = Query(20, ge=1, le=200, description="返回条数，1~200"),
    session: AsyncSession = Depends(get_session),
) -> WeatherHistoryResponse:
    http_client = request.app.state.http_client
    service = WeatherService(
        openweather_client=OpenWeatherClient(http_client),
        backup_client=BackupWeatherClient(http_client),
        session=session,
    )
    return await service.get_weather_history(city=city, limit=limit)
