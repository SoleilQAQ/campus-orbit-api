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
    jwxt_base_url: str = Field(
        "https://ysjw.sdufe.edu.cn:8081",  # 强智默认地址，你可以在 .env 里改
        alias="JWXT_BASE_URL",
    )
    # 是否忽略教务系统的 SSL 证书错误（证书过期时临时用）
    jwxt_insecure_ssl: bool = Field(
        True,
        alias="JWXT_INSECURE_SSL",
    )
    jwxt_connect_timeout: float = Field(
        10.0,
        alias="JWXT_CONNECT_TIMEOUT",
    )
    jwxt_read_timeout: float = Field(
        20.0,
        alias="JWXT_READ_TIMEOUT",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
