from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import secrets

from jose import jwt
from passlib.context import CryptContext

from .settings import platform_settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(pw: str) -> str:
    return pwd_context.hash(pw)


def verify_password(pw: str, pw_hash: str) -> bool:
    return pwd_context.verify(pw, pw_hash)


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
