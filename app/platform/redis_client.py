import json
from typing import Any, Optional

from redis.asyncio import Redis

from .settings import platform_settings


_redis: Optional[Redis] = None


def _redis_url() -> str:
    pwd = platform_settings.redis_password or ""
    auth = f":{pwd}@" if pwd else ""
    return f"redis://{auth}{platform_settings.redis_host}:{platform_settings.redis_port}/{platform_settings.redis_db}"


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(_redis_url(), decode_responses=True)
    return _redis


async def redis_get_json(key: str) -> Any:
    r = await get_redis()
    s = await r.get(key)
    return json.loads(s) if s else None


async def redis_set_json(key: str, value: Any, ttl_seconds: int | None = None) -> None:
    r = await get_redis()
    s = json.dumps(value, ensure_ascii=False)
    if ttl_seconds:
        await r.setex(key, ttl_seconds, s)
    else:
        await r.set(key, s)