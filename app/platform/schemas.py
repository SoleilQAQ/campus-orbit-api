from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class R(BaseModel):
    success: bool = True
    data: Any = None
    message: str = ""


class LoginReq(BaseModel):
    role: Literal["admin", "student"]
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)



class TokenData(BaseModel):
    """登录成功后返回的 token 数据"""
    model_config = ConfigDict(populate_by_name=True)

    username: str
    roles: list[str]
    accessToken: str = Field(..., alias="accessToken")
    refreshToken: str = Field(..., alias="refreshToken")
    expires: str

class LoginResp(BaseModel):
    model_config = ConfigDict(extra="ignore")

    success: bool
    message: str = ""
    data: TokenData | None = None   # ✅ 允许失败时 data=None

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


class AiConfigReq(BaseModel):
    """AI 配置请求"""
    enabled: bool = False
    apiUrl: str = ""
    apiToken: str = ""
    model: str = ""
    temperature: float = 0.7
    maxTokens: int = 2000
    promptTemplate: str = ""


class AiConfigResp(BaseModel):
    """AI 配置响应"""
    enabled: bool
    apiUrl: str
    apiToken: str
    model: str
    temperature: float
    maxTokens: int
    promptTemplate: str


# -------- 系统监控响应模型 --------
class SystemInfoData(BaseModel):
    """系统信息数据模型"""
    hostname: str
    os: str
    kernel: str
    arch: str
    ip: str
    bootTime: str
    uptimeSeconds: int


class ResourceUsageData(BaseModel):
    """资源使用率数据模型"""
    cpu: int = Field(..., ge=0, le=100)  # 0-100
    memory: int = Field(..., ge=0, le=100)  # 0-100
    disk: int = Field(..., ge=0, le=100)  # 0-100
    network: int = Field(..., ge=0, le=100)  # 0-100


class TrafficDataPoint(BaseModel):
    """流量数据点模型"""
    time: str
    inbound: int = Field(..., ge=0)
    outbound: int = Field(..., ge=0)


class CpuHistoryPoint(BaseModel):
    """CPU 历史数据点模型"""
    time: str
    usage: int = Field(..., ge=0, le=100)  # 0-100
