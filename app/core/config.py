# app/core/config.py
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 当前环境：dev / test / prod
    env: str = Field("dev", alias="ENV")

    # 数据库 URL（必须提供）
    database_url: str = Field(..., alias="DATABASE_URL")

    # OpenWeatherMap
    openweather_api_key: str = Field(..., alias="OPENWEATHER_API_KEY")
    openweather_base_url: str = Field(
        "http://api.openweathermap.org",
        alias="OPENWEATHER_BASE_URL",
    )

    # 备用天气接口
    backup_weather_url: str = Field(
        "http://weather.skkk.uno/api/weather",
        alias="BACKUP_WEATHER_URL",
    )

    # 天气缓存过期时间（分钟）
    weather_expiration_minutes: int = Field(
        30,
        alias="WEATHER_EXPIRATION_MINUTES",
    )

    # ==== 教务系统相关配置 ====
    # === 教务系统（academic） ===
    academic_base_url: str = Field(
        "http://ysjw.sdufe.edu.cn:8081",   # 默认用这个地址
        alias="ACADEMIC_BASE_URL",
    )
    academic_insecure_ssl: bool = Field(
        True,  # http 下其实无所谓，保留开关以后随时改成 https 也方便
        alias="ACADEMIC_INSECURE_SSL",
    )
    academic_connect_timeout: float = Field(
        10.0, alias="ACADEMIC_CONNECT_TIMEOUT"
    )
    academic_read_timeout: float = Field(
        20.0, alias="ACADEMIC_READ_TIMEOUT"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
