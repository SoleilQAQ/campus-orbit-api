import pytest

from app.main import app
from app.services.academic_service import get_academic_service


class FakeAcademicService:
    async def health(self, request_id=None):
        return {
            "success": True,
            "message": "mock ok",
            "source": "api",
            "data": {"reachable": True, "statusCode": 200},
            "timestamp": "2025-01-01T00:00:00Z",
        }


@pytest.mark.anyio
async def test_academic_health_mock(client):
    # 保留 conftest 里已有的 overrides，只覆盖这一项
    app.dependency_overrides[get_academic_service] = lambda: FakeAcademicService()
    try:
        r = await client.get("/api/academic/health")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["data"]["reachable"] is True
    finally:
        app.dependency_overrides.pop(get_academic_service, None)
