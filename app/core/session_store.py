from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from app.core.config import settings
from app.core.redis import get_redis


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class AcademicSession:
    session_id: str
    username: str
    cookies: Dict[str, str]
    created_at: datetime
    expires_at: datetime
    last_seen_at: datetime


class RedisAcademicSessionStore:
    """
    sessionId 由 Header: X-Academic-Session 传入

    - absolute_ttl：绝对过期（默认12h）
    - idle_ttl：空闲过期（默认30min，访问会续期）
    """

    def __init__(
        self,
        *,
        key_prefix: str = "academic:sess:",
        absolute_ttl_minutes: int | None = None,
        idle_ttl_minutes: int | None = None,
    ) -> None:
        self._redis = get_redis()
        self._key_prefix = key_prefix
        self._abs_min = absolute_ttl_minutes or settings.academic_session_absolute_ttl_minutes
        self._idle_min = idle_ttl_minutes or settings.academic_session_idle_ttl_minutes

    def _key(self, sid: str) -> str:
        return f"{self._key_prefix}{sid}"

    async def create(self, *, username: str, cookies: Dict[str, str]) -> AcademicSession:
        now = utc_now()
        sid = uuid.uuid4().hex
        expires_at = now + timedelta(minutes=self._abs_min)

        payload = {
            "session_id": sid,
            "username": username,
            "cookies": cookies,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "last_seen_at": now.isoformat(),
        }

        await self._redis.set(self._key(sid), json.dumps(payload, ensure_ascii=False), ex=self._idle_min * 60)

        return AcademicSession(
            session_id=sid,
            username=username,
            cookies=cookies,
            created_at=now,
            expires_at=expires_at,
            last_seen_at=now,
        )

    async def get(self, sid: str) -> Optional[AcademicSession]:
        if not sid:
            return None

        raw = await self._redis.get(self._key(sid))
        if not raw:
            return None

        try:
            data = json.loads(raw)
            created_at = datetime.fromisoformat(data["created_at"])
            expires_at = datetime.fromisoformat(data["expires_at"])
            last_seen_at = datetime.fromisoformat(data["last_seen_at"])
            cookies = dict(data.get("cookies") or {})
            username = str(data.get("username") or "")
        except Exception:
            await self._redis.delete(self._key(sid))
            return None

        now = utc_now()
        if now >= expires_at:
            await self._redis.delete(self._key(sid))
            return None

        # 滑动续期
        data["last_seen_at"] = now.isoformat()
        await self._redis.set(self._key(sid), json.dumps(data, ensure_ascii=False), ex=self._idle_min * 60)

        return AcademicSession(
            session_id=sid,
            username=username,
            cookies=cookies,
            created_at=created_at,
            expires_at=expires_at,
            last_seen_at=now,
        )

    async def delete(self, sid: str) -> None:
        if sid:
            await self._redis.delete(self._key(sid))


academic_session_store = RedisAcademicSessionStore()
