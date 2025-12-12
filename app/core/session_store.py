# app/core/session_store.py
from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class AcademicSession:
    session_id: str
    cookies: Dict[str, str]
    username: str
    expires_at: datetime
    created_at: datetime
    last_seen_at: datetime


class InMemoryAcademicSessionStore:
    def __init__(self, ttl_minutes: int = 60) -> None:
        self._ttl = timedelta(minutes=ttl_minutes)
        self._lock = asyncio.Lock()
        self._sessions: Dict[str, AcademicSession] = {}

    async def create(self, username: str, cookies: Dict[str, str]) -> AcademicSession:
        async with self._lock:
            sid = secrets.token_urlsafe(32)
            now = _utc_now()
            s = AcademicSession(
                session_id=sid,
                cookies=cookies,
                username=username,
                created_at=now,
                last_seen_at=now,
                expires_at=now + self._ttl,
            )
            self._sessions[sid] = s
            return s

    async def get(self, session_id: str) -> Optional[AcademicSession]:
        async with self._lock:
            s = self._sessions.get(session_id)
            if not s:
                return None
            if s.expires_at <= _utc_now():
                self._sessions.pop(session_id, None)
                return None
            # touch
            s.last_seen_at = _utc_now()
            return s

    async def delete(self, session_id: str) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)


# 单例（单机/单 worker 可用；多 worker 要换 Redis）
academic_session_store = InMemoryAcademicSessionStore(ttl_minutes=60)
