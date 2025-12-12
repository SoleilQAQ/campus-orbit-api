import pytest
from app.main import app
from app.services.academic_service import get_academic_service

class FakeAcademicService:
    async def login(self, username: str, password: str, request_id=None):
        return {
            "success": True,
            "message": "登录成功",
            "source": "api",
            "data": {"sessionId": "fake", "expiresAt": "2099-01-01T00:00:00Z"},
            "timestamp": "2025-01-01T00:00:00Z",
        }

@pytest.mark.anyio
async def test_academic_login_route(client):
    app.dependency_overrides[get_academic_service] = lambda: FakeAcademicService()
    try:
        r = await client.post("/api/academic/login", json={"username":"u","password":"p"})
        assert r.status_code == 200
        assert r.json()["success"] is True
    finally:
        app.dependency_overrides.pop(get_academic_service, None)