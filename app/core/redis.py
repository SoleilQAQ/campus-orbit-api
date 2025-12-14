from __future__ import annotations

from functools import lru_cache
import redis.asyncio as redis
from redis.asyncio import Redis

from app.core.config import settings


@lru_cache(maxsize=1)
def get_redis() -> Redis:
    if settings.redis_url:
        # URL 方式：支持 redis:// 和 rediss://，也支持 query 参数 decode_responses=True 等
        return redis.from_url(settings.redis_url, decode_responses=settings.redis_decode_responses)

    # 字段方式：支持 username/password（ACL），避免 URL 编码坑
    if not settings.redis_password:
        raise RuntimeError("REDIS_PASSWORD 未配置（或 REDIS_URL 未包含密码）")

    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        username=settings.redis_username,
        password=settings.redis_password,
        ssl=settings.redis_ssl,
        decode_responses=settings.redis_decode_responses,
    )
