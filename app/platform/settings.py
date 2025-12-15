from pydantic_settings import BaseSettings, SettingsConfigDict


class PlatformSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PLATFORM_", env_file=".env", extra="ignore")

    # JWT
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 120
    refresh_token_days: int = 30

    # Redis（需要密码）
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    # 登录策略
    student_auto_provision: bool = True  # 学生首次学号登录后是否自动创建账号（默认开）

    # 天气默认开关
    weather_enabled_default: bool = True

    # 初始管理员（用于 init_admin.py 脚本）
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = "admin123"


platform_settings = PlatformSettings()
