import pytest

from app.clients.weather_clients import OpenWeatherClient
from app.services.weather_service import WeatherService


@pytest.mark.asyncio
async def test_weather_ok(client, monkeypatch):
    # 1) mock 掉 OpenWeatherClient.get_current_weather（返回 OpenWeatherMap 原始结构）
    async def fake_get_current_weather(self, city: str):
        return {
            "coord": {"lon": 116.3972, "lat": 39.9075},
            "weather": [{"id": 804, "main": "Clouds", "description": "阴，多云", "icon": "04n"}],
            "main": {
                "temp": -2.06,
                "feels_like": -6.02,
                "temp_min": -2.06,
                "temp_max": -2.06,
                "pressure": 1039,
                "humidity": 22,
            },
            "visibility": 10000,
            "wind": {"speed": 3.05, "deg": 10},
            "clouds": {"all": 90},
            "sys": {"country": "CN", "sunrise": 1733960000, "sunset": 1733992000},
            "dt": 1734028800,
            "timezone": 28800,
            "name": city,
        }

    monkeypatch.setattr(OpenWeatherClient, "get_current_weather", fake_get_current_weather)

    # 2) mock 掉写库（避免测试依赖数据库）
    async def fake_persist(self, city: str, provider: str, data):
        return None

    monkeypatch.setattr(WeatherService, "_persist_snapshot_and_cache", fake_persist)

    # 3) 调你的接口
    r = await client.get("/api/weather", params={"city": "beijing"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
