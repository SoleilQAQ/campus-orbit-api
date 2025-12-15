from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class R(BaseModel):
    success: bool = True
    data: Any = None
    message: str = ""


class LoginReq(BaseModel):
    role: Literal["admin", "student"]
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenData(BaseModel):
    username: str
    roles: list[str]
    accessToken: str
    refreshToken: str
    expires: str


class LoginResp(R):
    data: TokenData


class MeResp(R):
    data: dict


class AdminUserItem(BaseModel):
    id: str
    username: str
    role: str
    student_id: Optional[str] = None
    is_enabled: bool


class ToggleReq(BaseModel):
    enabled: bool


class WeatherBackupSetReq(BaseModel):
    payload: dict


class PromptItem(BaseModel):
    id: str
    name: str
    content: str


class AnalyzeReq(BaseModel):
    semester: str = ""
    prompt_id: Optional[str] = None
    extra_prompt: str = ""
