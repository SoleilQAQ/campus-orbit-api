# app/schemas/academic.py
from pydantic import BaseModel
from datetime import datetime


class JwxtLoginRequest(BaseModel):
    username: str
    password: str


class JwxtLoginResponse(BaseModel):
    success: bool
    message: str


class JwxtUserProfile(BaseModel):
    student_id: str
    name: str
    college: str | None = None
    major: str | None = None
    clazz: str | None = None
    enrollment_year: str | None = None
    study_level: str | None = None
    # 后续可加 last_synced_at、updated_at 等
    last_synced_at: datetime | None = None
