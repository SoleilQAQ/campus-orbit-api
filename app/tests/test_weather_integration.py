import os
import pytest

from app.clients.weather_clients import OpenWeatherClient

pytestmark = pytest.mark.integration

def _has_db_url() -> bool:
    return bool(os.getenv("DATABASE_URL"))

@pytest.mark.asyncio
async def test_weather_write_and_history(client, monkeypatch):
    if not _has_db_url():
        pytest.skip("DATABASE_URL not set; integration test requires Postgres.")

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

    r1 = await client.get("/api/weather", params={"city": "beijing"})
    assert r1.status_code == 200
    assert r1.json()["success"] is True

    r2 = await client.get("/api/weather/history", params={"city": "beijing", "limit": 5})
    assert r2.status_code == 200
    body = r2.json()
    assert body["success"] is True
    assert body["count"] >= 1
    assert body["items"][0]["city"].lower() == "beijing"
