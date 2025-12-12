# app/api/weather.py
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.clients.weather_clients import (
    OpenWeatherClient,
    BackupWeatherClient,
)
from app.services.weather_service import WeatherService
from app.models.weather_schemas import WeatherResponse


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
