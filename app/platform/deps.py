import uuid
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from .security import decode_token
from .db_compat import get_db


oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(token: str = Depends(oauth2), db=Depends(get_db)):
    from .models import PlatformUser  # 避免循环导入
    try:
        payload = decode_token(token)
        user_id = uuid.UUID(payload["sub"])
        role = payload["role"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    u = await db.get(PlatformUser, user_id)
    if not u:
        raise HTTPException(status_code=401, detail="User not found")
    if not u.is_enabled:
        raise HTTPException(status_code=403, detail="User disabled")
    return u


def require_role(*roles: str):
    async def _dep(u=Depends(get_current_user)):
        if u.role not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return u
    return _dep
