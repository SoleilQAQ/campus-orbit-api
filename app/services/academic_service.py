from __future__ import annotations
import logging
from typing import Optional, Dict, Any

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.academic_client import AcademicClient
from app.core.session_store import academic_session_store, AcademicSession
from app.repositories.academic_repo import AcademicRepo
from datetime import datetime, timezone

from app.db.session import get_session

logger = logging.getLogger(__name__)

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

class AcademicService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = AcademicRepo(db)
        self.client = AcademicClient()

    async def health(self, *, request_id: Optional[str] = None) -> Dict[str, Any]:
        r = await self.client.fetch_health(request_id=request_id)
        return {
            "success": True,
            "status_code": r.status_code,
            "url": r.url,
            "location": r.location,
            "content_type": r.content_type,
            "content_length": r.content_length,
            "text_sample": r.text_sample,
        }

    async def login(self, *, username: str, password: str, request_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            r = await self.client.login(username=username, password=password, request_id=request_id)
            if not r.success:
                return {
                    "success": False,
                    "message": "登录失败",
                    "data": {
                        "statusCode": r.status_code,
                        "redirectLocation": r.location,
                        "htmlSample": r.text_sample,
                    },
                    "timestamp": _utc_now_iso(),
                }

            session = await academic_session_store.create(username=username, cookies=r.cookies)
            return {
                "success": True,
                "message": "登录成功",
                "data": {
                    "sessionId": session.session_id,
                    "expiresAt": session.expires_at.isoformat().replace("+00:00", "Z"),
                    "statusCode": r.status_code,
                    "location": r.location,
                },
                "timestamp": _utc_now_iso(),
            }
        except Exception as e:
            logger.exception("教务系统 login 失败: %s", e)
            return {
                "success": False,
                "message": f"无法连接教务系统: {e}",
                "data": None,
                "timestamp": _utc_now_iso(),
            }

    async def logout(self, *, session_id: str) -> Dict[str, Any]:
        await academic_session_store.delete(session_id)
        return {"success": True}

    async def _require_session(self, session_id: str) -> AcademicSession:
        s = await academic_session_store.get(session_id)
        if s is None:
            raise HTTPException(status_code=401, detail={"reason": "SESSION_INVALID"})
        return s

    async def me(self, *, session_id: str, request_id: Optional[str] = None, refresh: bool = False) -> Dict[str, Any]:
        s = await self._require_session(session_id)

        if not refresh:
            cached = await self.repo.get_cached_me(s.username)
            if cached:
                return {"success": True, "data": cached, "cached": True}

        r = await self.client.fetch_me(cookies=s.cookies, request_id=request_id)
        if not r.get("success"):
            cached = await self.repo.get_cached_me(s.username)
            if cached:
                return {"success": True, "data": cached, "cached": True, "fallback": True, **r}
            raise HTTPException(status_code=401, detail=r)

        try:
            await self.repo.save_me(student_id=s.username, account=s.username, me_data=r["data"])
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

        return {"success": True, "data": r["data"], "cached": False}

    async def semesters(self, *, session_id: str, request_id: Optional[str] = None, refresh: bool = False) -> Dict[str, Any]:
        s = await self._require_session(session_id)

        if not refresh:
            cached = await self.repo.get_cached_semesters(s.username)
            if cached:
                return {"success": True, **cached, "cached": True}

        r = await self.client.fetch_semesters(cookies=s.cookies, request_id=request_id)
        if not r.get("success"):
            cached = await self.repo.get_cached_semesters(s.username)
            if cached:
                return {"success": True, **cached, "cached": True, "fallback": True, **r}
            raise HTTPException(status_code=401, detail=r)

        try:
            await self.repo.save_semesters(student_id=s.username, account=s.username, payload=r)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

        return {"success": True, **r, "cached": False}

    async def grades(self, *, session_id: str, semester: str = "", request_id: Optional[str] = None, refresh: bool = False) -> Dict[str, Any]:
        s = await self._require_session(session_id)

        if not refresh:
            cached = await self.repo.get_cached_grades(s.username, semester)
            if cached:
                return {"success": True, **cached, "cached": True}

        r = await self.client.fetch_grades(cookies=s.cookies, semester=semester, request_id=request_id)
        if not r.get("success"):
            cached = await self.repo.get_cached_grades(s.username, semester)
            if cached:
                return {"success": True, **cached, "cached": True, "fallback": True, **r}
            raise HTTPException(status_code=401, detail=r)

        try:
            await self.repo.save_grades(student_id=s.username, account=s.username, semester=semester, payload=r)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

        return {"success": True, **r, "cached": False}

    async def schedule(self, *, session_id: str, xnxq: str = "", request_id: Optional[str] = None, refresh: bool = False) -> Dict[str, Any]:
        s = await self._require_session(session_id)

        if not refresh:
            cached = await self.repo.get_cached_schedule(s.username, xnxq)
            if cached:
                return {"success": True, **cached, "cached": True}

        r = await self.client.fetch_schedule(cookies=s.cookies, xnxq=xnxq, request_id=request_id)
        if not r.get("success"):
            cached = await self.repo.get_cached_schedule(s.username, xnxq)
            if cached:
                return {"success": True, **cached, "cached": True, "fallback": True, **r}
            raise HTTPException(status_code=401, detail=r)

        try:
            await self.repo.save_schedule(student_id=s.username, account=s.username, xnxq=xnxq, payload=r)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

        return {"success": True, **r, "cached": False}


def get_academic_service(db: AsyncSession = Depends(get_session)):  # type: ignore[misc]
    return AcademicService(db=db)
