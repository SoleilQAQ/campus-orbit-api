# app/schemas/academic_schemas.py
from pydantic import BaseModel, Field


class AcademicLoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class AcademicLoginData(BaseModel):
    sessionId: str
    expiresAt: str
