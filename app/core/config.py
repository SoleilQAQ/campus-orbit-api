# app/core/config.py
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    全局配置：
    - 优先从环境变量读取
    - 其次从 .env 读取
    - 最后才用默认值（非敏感）
    """

    # 数据库 URL（必须提供，不给默认，防止把错误的开发库写死）
    database_url: str = Field(..., alias="DATABASE_URL")

    # OpenWeatherMap API Key（必须提供）
    openweather_api_key: str = Field(..., alias="OPENWEATHER_API_KEY")

    # OpenWeatherMap 基础 URL（非敏感，给默认即可）
    openweather_base_url: str = Field(
        default="https://api.openweathermap.org",
        alias="OPENWEATHER_BASE_URL",
    )

    # 备用天气接口（你的服务）
    backup_weather_url: str = Field(
        default="http://weather.skkk.uno/api/weather",
        alias="BACKUP_WEATHER_URL",
    )

    # 缓存过期时间（分钟）
    weather_expiration_minutes: int = Field(
        default=30,
        alias="WEATHER_EXPIRATION_MINUTES",
    )

    # 后面要接教务系统 / JWT 等，也可以在这里继续加：
    # jwxt_base_url: str = Field("https://ysjw.sdufe.edu.cn:8081", alias="JWXT_BASE_URL")
    # jwxt_insecure_ssl: bool = Field(True, alias="JWXT_INSECURE_SSL")
    # secret_key: str = Field(..., alias="SECRET_KEY")

    # Pydantic Settings 配置
    model_config = SettingsConfigDict(
        env_file=".env",  # 自动从 .env 读取
        env_file_encoding="utf-8",
        extra="ignore",  # 忽略多余的环境变量
    )


settings = Settings()
