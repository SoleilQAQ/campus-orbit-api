# app/tests/conftest.py
import httpx
import pytest_asyncio
from asgi_lifespan import LifespanManager

from app.main import app  # 按你的实际入口改：比如 from app.main import app


@pytest_asyncio.fixture
async def client():
    """
    提供一个可用于 async 测试的 HTTP 客户端：
    - 触发 FastAPI lifespan（startup/shutdown）
    - 用 httpx.ASGITransport 直接调用 ASGI app，不用起服务器
    """
    async with LifespanManager(app):  # AsyncClient 不会触发 lifespan，需要这个 :contentReference[oaicite:2]{index=2}
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as ac:
            yield ac