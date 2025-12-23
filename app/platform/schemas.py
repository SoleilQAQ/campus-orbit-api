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
    expires: int  # 毫秒时间戳，前端更容易处理

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


# -------- 天气配置模型 --------
class WeatherProviderFieldMapping(BaseModel):
    """天气提供商字段映射"""
    temperature: str = "main.temp"
    humidity: str = "main.humidity"
    description: str = "weather[0].description"
    icon: str = "weather[0].icon"
    wind_speed: str = "wind.speed"
    city: str = "name"


class WeatherProviderConfig(BaseModel):
    """天气提供商配置"""
    id: str
    name: str
    enabled: bool = True
    priority: int = 1
    api_url: str
    api_key: str = ""
    field_mapping: WeatherProviderFieldMapping = Field(default_factory=WeatherProviderFieldMapping)
    request_params: dict = Field(default_factory=dict)


class WeatherFallbackData(BaseModel):
    """天气备用数据"""
    city: str = "北京"
    temperature: float = 20.0
    humidity: int = 50
    description: str = "晴"


class WeatherConfigData(BaseModel):
    """天气配置数据"""
    enabled: bool = True
    providers: list[WeatherProviderConfig] = Field(default_factory=list)
    fallback_data: Optional[WeatherFallbackData] = None
    cache_minutes: int = 30
    timeout_seconds: int = 10


class WeatherConfigReq(BaseModel):
    """天气配置请求"""
    enabled: bool = True
    providers: list[WeatherProviderConfig] = Field(default_factory=list)
    fallback_data: Optional[WeatherFallbackData] = None
    cache_minutes: int = 30
    timeout_seconds: int = 10


class WeatherTestReq(BaseModel):
    """天气接口测试请求"""
    provider_id: str
    city: str


class WeatherMappedData(BaseModel):
    """映射后的天气数据"""
    temperature: Optional[float] = None
    humidity: Optional[int] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    wind_speed: Optional[float] = None
    city: Optional[str] = None


class WeatherTestResult(BaseModel):
    """天气接口测试结果"""
    raw_response: dict
    mapped_data: WeatherMappedData
    response_time_ms: int
