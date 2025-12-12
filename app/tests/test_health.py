import pytest

@pytest.mark.asyncio
async def test_liveness(client):
    r = await client.get("/api/health/liveness")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"