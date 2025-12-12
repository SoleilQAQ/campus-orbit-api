# app/core/db.py
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.config import settings


# SQLAlchemy 异步 Engine
engine = create_async_engine(
    settings.database_url,
    echo=True,  # 开发调试可以改成 True
    future=True,
)

# Session 工厂
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


# FastAPI 依赖：在路由里用 Depends(get_session)
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
