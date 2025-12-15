# app/tests/conftest.py
from __future__ import annotations

import httpx
import pytest_asyncio
from asgi_lifespan import LifespanManager

from app.main import app
from app.db.session import AsyncSessionLocal, get_session


async def _override_get_session():
    """
    测试环境专用 DB 依赖：
    - 每次依赖调用创建一个新的 AsyncSession
    - 用 async with 确保用完就正确关闭
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            # context manager 退出时其实会自动处理，这里只是语义更清晰
            await session.close()


@pytest_asyncio.fixture
async def client():
    """
    提供一个可用于 async 测试的 HTTP 客户端：
    - 触发 FastAPI lifespan（startup/shutdown）
    - 覆盖 get_session，避免多个请求/协程复用同一个 Session
    - 仍然使用原来的 ASGITransport 写法
    """
    # 覆盖 FastAPI 中的 DB 依赖
    app.dependency_overrides[get_session] = _override_get_session

    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as ac:
            yield ac

    # 测完清理覆盖，避免影响其他测试
    app.dependency_overrides.clear()
