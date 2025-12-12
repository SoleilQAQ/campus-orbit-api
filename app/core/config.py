# app/core/config.py
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

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
        "https://ysjw.sdufe.edu.cn:8081",   # 默认用这个地址
        validation_alias="ACADEMIC_BASE_URL",
    )
    academic_insecure_ssl: bool = Field(
        True,  # http 下其实无所谓，保留开关以后随时改成 https 也方便
        validation_alias="ACADEMIC_INSECURE_SSL",
    )
    academic_connect_timeout: float = Field(
        10.0, validation_alias="ACADEMIC_CONNECT_TIMEOUT"
    )
    academic_read_timeout: float = Field(
        20.0, validation_alias="ACADEMIC_READ_TIMEOUT"
    )
    # 建议：默认 False；需要临时绕过证书才设 True（尤其你未来可能切回 https）
    academic_insecure_skip_verify: bool = Field(
        default=False,
        validation_alias="ACADEMIC_INSECURE_SSL",
    )
    # health 用哪个 path（先测登录入口最稳）
    academic_health_path: str = Field(
        default="/jsxsd/xk/LoginToXk",
        validation_alias="ACADEMIC_HEALTH_PATH",
    )
    academic_user_agent: str = Field(
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0"
        ),
        validation_alias="ACADEMIC_USER_AGENT",
    )

settings = Settings()
