import os
import pytest

pytestmark = pytest.mark.integration

@pytest.mark.asyncio
async def test_readiness_db(client):
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")
    r = await client.get("/api/health/readiness")
    assert r.status_code == 200
    assert r.json()["db"] == "ok"
