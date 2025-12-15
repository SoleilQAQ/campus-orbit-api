from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import PlatformUser, WeatherSwitch, AiPromptTemplate, AiAnalysisHistory


class PlatformRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_by_username(self, username: str) -> PlatformUser | None:
        q = await self.db.execute(select(PlatformUser).where(PlatformUser.username == username))
        return q.scalar_one_or_none()

    async def create_user(self, *, username: str, role: str, student_id: str | None, password_hash: str | None) -> PlatformUser:
        u = PlatformUser(username=username, role=role, student_id=student_id, password_hash=password_hash, is_enabled=True)
        self.db.add(u)
        await self.db.flush()
        return u

    async def list_users(self, role: str | None = None) -> list[PlatformUser]:
        stmt = select(PlatformUser).order_by(PlatformUser.created_at.desc())
        if role:
            stmt = stmt.where(PlatformUser.role == role)
        q = await self.db.execute(stmt)
        return list(q.scalars().all())

    async def set_user_enabled(self, user_id, enabled: bool) -> None:
        u = await self.db.get(PlatformUser, user_id)
        if not u:
            return
        u.is_enabled = enabled
        await self.db.flush()

    async def get_or_create_weather_switch(self, enabled_default: bool) -> WeatherSwitch:
        q = await self.db.execute(select(WeatherSwitch).limit(1))
        ws = q.scalar_one_or_none()
        if ws:
            return ws
        ws = WeatherSwitch(enabled=enabled_default)
        self.db.add(ws)
        await self.db.flush()
        return ws

    async def get_prompts(self, role: str = "student") -> list[AiPromptTemplate]:
        q = await self.db.execute(
            select(AiPromptTemplate).where(AiPromptTemplate.role == role, AiPromptTemplate.is_enabled == True)  # noqa
        )
        return list(q.scalars().all())

    async def get_prompt_by_id(self, pid) -> AiPromptTemplate | None:
        return await self.db.get(AiPromptTemplate, pid)

    async def add_analysis(self, hist: AiAnalysisHistory) -> None:
        self.db.add(hist)
        await self.db.flush()
