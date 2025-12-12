# app/services/academic_service.py
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from app.clients.academic_client import AcademicClient
from app.core.session_store import academic_session_store

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class AcademicService:
    def __init__(self) -> None:
        self.client = AcademicClient()

    async def health(self, request_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            r = await self.client.fetch_health(request_id=request_id)

            reachable = 200 <= r.status_code < 500  # 302/403 也算“能连上”
            msg = "教务系统可达" if reachable else "教务系统不可达"

            return {
                "success": reachable,
                "message": msg,
                "source": "api",
                "data": {
                    "reachable": reachable,
                    "statusCode": r.status_code,
                    "url": r.url,
                    "redirectLocation": r.location,
                    "htmlSample": r.text_sample,
                    "contentLength": r.content_length,
                    "contentType": r.content_type
                },
                "timestamp": _utc_now_iso(),
            }
        except Exception as e:
            logger.exception("教务系统 health 探测失败: %s", e)
            return {
                "success": False,
                "message": f"无法连接教务系统: {e}",
                "source": None,
                "data": None,
                "timestamp": _utc_now_iso(),
            }

    async def login(self, username: str, password: str, request_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            r = await self.client.login(username=username, password=password, request_id=request_id)

            if not r.success:
                return {
                    "success": False,
                    "message": "登录失败（可能需要 encoded 加密参数）",
                    "source": "api",
                    "data": {
                        "statusCode": r.status_code,
                        "redirectLocation": r.location,
                        "htmlSample": r.text_sample,
                    },
                    "timestamp": _utc_now_iso(),
                }

            s = await academic_session_store.create(username=username, cookies=r.cookies)
            return {
                "success": True,
                "message": "登录成功",
                "source": "api",
                "data": {
                    "sessionId": s.session_id,
                    "expiresAt": s.expires_at.isoformat().replace("+00:00", "Z"),
                },
                "timestamp": _utc_now_iso(),
            }
        except Exception as e:
            logger.exception("教务系统 login 失败: %s", e)
            return {
                "success": False,
                "message": f"无法连接教务系统: {e}",
                "source": None,
                "data": None,
                "timestamp": _utc_now_iso(),
            }

def get_academic_service() -> AcademicService:
    return AcademicService()
