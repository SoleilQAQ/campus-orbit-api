from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

# 兼容：优先复用你项目已有的 get_async_session / Base
from app.db.session import get_session as _get_async_session

from app.db.base import Base

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if _get_async_session is None:
        raise RuntimeError("找不到 app.db.session.get_session")
    async for s in _get_async_session():
        yield s
