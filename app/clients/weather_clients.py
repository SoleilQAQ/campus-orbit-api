# app/clients/weather_clients.py
from __future__ import annotations

from typing import Dict, Any

import httpx

from app.core.config import settings
from app.schemas.weather_schemas import WeatherResponse


class OpenWeatherClient:
    def __init__(self, http_client: httpx.AsyncClient):
        self.http_client = http_client
        self.base_url = settings.openweather_base_url
        self.api_key = settings.openweather_api_key

    async def get_current_weather(self, city: str) -> Dict[str, Any]:
        if not self.api_key:
            # 这里你可以换成自定义异常
            raise RuntimeError("OPENWEATHER_API_KEY 未配置")

        params = {
            "q": city,
            "appid": self.api_key,
            "units": "metric",
            "lang": "zh_cn",
        }
        resp = await self.http_client.get(
            f"{self.base_url}/data/2.5/weather", params=params
        )
        resp.raise_for_status()
        return resp.json()


class BackupWeatherClient:
    """
    调用你的备用接口 http://weather.skkk.uno/api/weather?city=...
    这个接口返回的数据结构已经是 WeatherResponse 的格式
    """

    def __init__(self, http_client: httpx.AsyncClient):
        self.http_client = http_client
        self.base_url = settings.backup_weather_url

    async def get_weather(self, city: str) -> WeatherResponse:
        resp = await self.http_client.get(
            self.base_url,
            params={"city": city},
            timeout=5.0,
        )
        # 如果对方返回非 200，这里会抛异常，由上层兜底
        resp.raise_for_status()
        data = resp.json()
        # 直接解析成 WeatherResponse（data 里会是 WeatherData）
        return WeatherResponse.model_validate(data)
