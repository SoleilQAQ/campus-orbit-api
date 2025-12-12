from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/liveness")
async def liveness():
    # 进程活着就算 OK（给 k8s/ALB 用）
    return {"status": "ok"}


@router.get("/readiness")
async def readiness(session: AsyncSession = Depends(get_session)):
    # 依赖就绪（至少 DB 可用）
    await session.execute(text("SELECT 1"))
    return {"status": "ok", "db": "ok"}
