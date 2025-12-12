# app/api/academic.py
from fastapi import APIRouter
from app.schemas.academic import JwxtLoginRequest, JwxtLoginResponse
from app.services.academic_service import JwxtService

router = APIRouter(prefix="/api/jwxt", tags=["jwxt"])


@router.post("/login", response_model=JwxtLoginResponse)
async def jwxt_login(body: JwxtLoginRequest) -> JwxtLoginResponse:
    """
    教务系统登录入口（后端统一）：
    - 未来会做两件事：
      1. 调用教务系统登录
      2. 登录成功后，拉取个人信息并同步到本地数据库
    """
    service = JwxtService()
    ok, msg = await service.login(body.username, body.password)

    return JwxtLoginResponse(
        success=ok,
        message=msg,
    )
