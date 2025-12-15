import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from .db_compat import get_db
from .schemas import R, LoginReq, LoginResp, ToggleReq, WeatherBackupSetReq, AnalyzeReq
from .repo import PlatformRepo
from .services import AuthService, WeatherSwitchService, StudentService
from .deps import get_current_user, require_role
from  app.services import weather_service

router = APIRouter(prefix="/api", tags=["platform"])

@router.post("/auth/login", response_model=LoginResp)
async def login(req: LoginReq, db: AsyncSession = Depends(get_db)):
    svc = AuthService(db)
    if req.role == "admin":
        res = await svc.login_admin(req.username, req.password)
    else:
        res = await svc.login_student(req.username, req.password)

    if not res["ok"]:
        return LoginResp(success=False, data=None, message=res["msg"])

    return LoginResp(success=True, data=res["data"], message="")


@router.get("/auth/me")
async def me(u=Depends(get_current_user)):
    return R(success=True, data={"id": str(u.id), "username": u.username, "role": u.role, "student_id": u.student_id})


# -------- Admin: 用户管理 --------
@router.get("/admin/users")
async def admin_list_users(role: str | None = Query(None), db: AsyncSession = Depends(get_db), _=Depends(require_role("admin"))):
    repo = PlatformRepo(db)
    users = await repo.list_users(role=role)
    data = [
        {"id": str(x.id), "username": x.username, "role": x.role, "student_id": x.student_id, "is_enabled": x.is_enabled}
        for x in users
    ]
    return R(success=True, data=data)


@router.patch("/admin/users/{user_id}/enable")
async def admin_enable_user(user_id: uuid.UUID, req: ToggleReq, db: AsyncSession = Depends(get_db), _=Depends(require_role("admin"))):
    repo = PlatformRepo(db)
    await repo.set_user_enabled(user_id, req.enabled)
    await db.commit()
    return R(success=True, data={"user_id": str(user_id), "enabled": req.enabled})


# -------- Admin: 天气开关 + 备份 --------
@router.get("/admin/weather/switch")
async def admin_get_weather_switch(db: AsyncSession = Depends(get_db), _=Depends(require_role("admin"))):
    svc = WeatherSwitchService(db)
    return R(success=True, data=await svc.get_switch())


@router.put("/admin/weather/switch")
async def admin_set_weather_switch(req: ToggleReq, db: AsyncSession = Depends(get_db), _=Depends(require_role("admin"))):
    svc = WeatherSwitchService(db)
    data = await svc.set_switch(req.enabled)
    await db.commit()
    return R(success=True, data=data)


@router.get("/admin/weather/backup")
async def admin_get_weather_backup(db: AsyncSession = Depends(get_db), _=Depends(require_role("admin"))):
    svc = WeatherSwitchService(db)
    return R(success=True, data=await svc.get_backup_payload())


@router.put("/admin/weather/backup")
async def admin_set_weather_backup(req: WeatherBackupSetReq, db: AsyncSession = Depends(get_db), _=Depends(require_role("admin"))):
    svc = WeatherSwitchService(db)
    await svc.set_backup_payload(req.payload)
    await db.commit()
    return R(success=True, data=True)


# -------- Public: 天气接口（受开关控制）--------
@router.get("/weather/current")
async def weather_current(city: str = Query(..., min_length=1), db: AsyncSession = Depends(get_db), u=Depends(get_current_user)):
    svc = WeatherSwitchService(db)
    sw = await svc.get_switch()
    if not sw["enabled"]:
        raise HTTPException(status_code=503, detail="Weather API disabled by admin")

    weather_service.get_weather_by_city(city)
    return R(success=True, data={"city": city, "note": "这里请接你现有 weather_service 的返回"}, message="")


# -------- Student: 信息/成绩/AI --------
@router.get("/student/profile")
async def student_profile(db: AsyncSession = Depends(get_db), u=Depends(require_role("student"))):
    svc = StudentService(db, u.id)
    res = await svc.get_profile()
    if not res["ok"]:
        return R(success=False, data=None, message=res["msg"])
    return R(success=True, data=res["data"])


@router.get("/student/semesters")
async def student_semesters(db: AsyncSession = Depends(get_db), u=Depends(require_role("student"))):
    svc = StudentService(db, u.id)
    res = await svc.get_semesters()
    if not res["ok"]:
        return R(success=False, data=None, message=res["msg"])
    return R(success=True, data=res["data"])


@router.get("/student/grades")
async def student_grades(semester: str = "", db: AsyncSession = Depends(get_db), u=Depends(require_role("student"))):
    svc = StudentService(db, u.id)
    res = await svc.get_grades(semester)
    if not res["ok"]:
        return R(success=False, data=None, message=res["msg"])
    return R(success=True, data=res["data"])


@router.get("/student/schedule")
async def student_schedule(xnxq: str = "", db: AsyncSession = Depends(get_db), u=Depends(require_role("student"))):
    svc = StudentService(db, u.id)
    res = await svc.get_schedule(xnxq)
    if not res["ok"]:
        return R(success=False, data=None, message=res["msg"])
    return R(success=True, data=res["data"])


@router.get("/student/ai/prompts")
async def student_prompts(db: AsyncSession = Depends(get_db), u=Depends(require_role("student"))):
    repo = PlatformRepo(db)
    ps = await repo.get_prompts(role="student")
    data = [{"id": str(p.id), "name": p.name, "content": p.content} for p in ps]
    return R(success=True, data=data)


@router.post("/student/ai/analyze")
async def student_ai_analyze(req: AnalyzeReq, db: AsyncSession = Depends(get_db), u=Depends(require_role("student"))):
    repo = PlatformRepo(db)
    prompt_name = "默认分析"
    prompt_text = req.extra_prompt or ""

    if req.prompt_id:
        p = await repo.get_prompt_by_id(uuid.UUID(req.prompt_id))
        if p:
            prompt_name = p.name
            prompt_text = (p.content or "") + ("\n" + prompt_text if prompt_text else "")

    svc = StudentService(db, u.id)
    grades = await svc.get_grades(req.semester)
    if not grades["ok"]:
        return R(success=False, data=None, message=grades["msg"])

    out = await svc.ai_analyze(
        semester=req.semester,
        prompt_name=prompt_name,
        prompt_text=prompt_text,
        grades_payload=grades["data"],
    )
    await db.commit()
    return R(success=True, data={"text": out})
