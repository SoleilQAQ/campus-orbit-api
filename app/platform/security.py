from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import secrets
import asyncio

from jose import jwt
import hashlib
from passlib.context import CryptContext

from .settings import platform_settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _bcrypt_input(raw: str) -> str:
    """
    bcrypt only uses first 72 BYTES.
    To avoid truncation issues (and weird unicode byte-length surprises),
    we pre-hash with SHA-256 to a fixed-size ASCII string.
    """
    raw_bytes = raw.encode("utf-8")
    digest = hashlib.sha256(raw_bytes).hexdigest()  # 64 chars ASCII
    return digest


def hash_password(raw: str) -> str:
    """同步版本的密码哈希（用于初始化等场景）"""
    return pwd_context.hash(_bcrypt_input(raw))


async def hash_password_async(raw: str) -> str:
    """异步版本的密码哈希（避免阻塞事件循环）"""
    return await asyncio.to_thread(pwd_context.hash, _bcrypt_input(raw))


def verify_password(raw: str, hashed: str) -> bool:
    """同步版本的密码验证"""
    return pwd_context.verify(_bcrypt_input(raw), hashed)


async def verify_password_async(raw: str, hashed: str) -> bool:
    """异步版本的密码验证（避免阻塞事件循环）"""
    return await asyncio.to_thread(pwd_context.verify, _bcrypt_input(raw), hashed)


def create_access_token(subject: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=platform_settings.access_token_minutes)
    payload: Dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, platform_settings.jwt_secret_key, algorithm=platform_settings.jwt_algorithm)


def create_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, platform_settings.jwt_secret_key, algorithms=[platform_settings.jwt_algorithm])
