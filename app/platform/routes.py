import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from .db_compat import get_db
from .schemas import (
    R, LoginReq, LoginResp, ToggleReq, WeatherBackupSetReq, AnalyzeReq, AiConfigReq,
    WeatherConfigReq, WeatherTestReq, WeatherMappedData, WeatherTestResult
)
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


# -------- Query: 学生信息查询 --------
@router.get("/query/student")
async def query_student(
    keyword: str = Query(..., min_length=1, description="搜索关键字（学号、姓名、班级、专业）"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)  # 需要登录才能查询
):
    """
    根据关键字搜索学生信息
    支持按学号、姓名、班级、专业模糊搜索
    """
    repo = PlatformRepo(db)
    data = await repo.search_students(keyword)
    return R(success=True, data=data)


# -------- Admin: 用户管理 --------
@router.get("/admin/users")
async def admin_list_users(role: str | None = Query(None), db: AsyncSession = Depends(get_db), _=Depends(require_role("admin"))):
    """获取用户列表，返回前端需要的字段格式"""
    repo = PlatformRepo(db)
    users = await repo.list_users(role=role)
    
    # 获取学生详细信息（从 academic_user 表）
    from app.models.academic_models import AcademicUser
    from sqlalchemy import select
    
    data = []
    for x in users:
        # 前端字段：学号、姓名、班级、专业、年级、登录状态
        item = {
            "id": str(x.id),
            "studentId": x.student_id or x.username,  # 学号
            "name": None,  # 姓名
            "className": None,  # 班级
            "major": None,  # 专业
            "grade": None,  # 年级（入学年份）
            "isEnabled": x.is_enabled,  # 登录状态
        }
        
        # 如果是学生，尝试获取教务系统缓存的详细信息
        if x.role == "student" and x.student_id:
            q = await db.execute(
                select(AcademicUser).where(AcademicUser.student_id == x.student_id)
            )
            acad_user = q.scalar_one_or_none()
            if acad_user:
                item["name"] = acad_user.name
                item["className"] = acad_user.class_name
                item["major"] = acad_user.major
                item["grade"] = acad_user.enrollment_year
        
        data.append(item)
    
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


# -------- Admin: 天气配置 --------
@router.get("/admin/weather/config")
async def admin_get_weather_config(db: AsyncSession = Depends(get_db), _=Depends(require_role("admin"))):
    """获取天气配置"""
    repo = PlatformRepo(db)
    cfg = await repo.get_or_create_weather_config()
    await db.commit()
    return R(success=True, data={
        "enabled": cfg.enabled,
        "providers": cfg.providers,
        "fallback_data": cfg.fallback_data,
        "cache_minutes": cfg.cache_minutes,
        "timeout_seconds": cfg.timeout_seconds,
    })


@router.put("/admin/weather/config")
async def admin_set_weather_config(req: WeatherConfigReq, db: AsyncSession = Depends(get_db), _=Depends(require_role("admin"))):
    """更新天气配置"""
    repo = PlatformRepo(db)
    
    # 转换 providers 为字典列表
    providers_data = [p.model_dump() for p in req.providers]
    fallback_data = req.fallback_data.model_dump() if req.fallback_data else None
    
    cfg = await repo.update_weather_config(
        enabled=req.enabled,
        providers=providers_data,
        fallback_data=fallback_data,
        cache_minutes=req.cache_minutes,
        timeout_seconds=req.timeout_seconds,
    )
    await db.commit()
    return R(success=True, data={
        "enabled": cfg.enabled,
        "providers": cfg.providers,
        "fallback_data": cfg.fallback_data,
        "cache_minutes": cfg.cache_minutes,
        "timeout_seconds": cfg.timeout_seconds,
    })


@router.post("/admin/weather/test")
async def admin_test_weather(
    request: Request,
    req: WeatherTestReq,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role("admin"))
):
    """测试天气接口"""
    import time
    import httpx
    from .weather_utils import map_weather_response
    
    repo = PlatformRepo(db)
    cfg = await repo.get_or_create_weather_config()
    
    # 查找指定的 provider
    provider = None
    for p in cfg.providers:
        if p.get("id") == req.provider_id:
            provider = p
            break
    
    if not provider:
        return R(success=False, data=None, message=f"未找到提供商: {req.provider_id}")
    
    if not provider.get("api_url"):
        return R(success=False, data=None, message="API URL 未配置")
    
    # 构建请求参数
    params = dict(provider.get("request_params", {}))
    params["q"] = req.city
    
    # 添加 API Key（如果有）
    api_key = provider.get("api_key")
    if api_key:
        params["appid"] = api_key
    
    try:
        start_time = time.time()
        
        async with httpx.AsyncClient(timeout=cfg.timeout_seconds) as client:
            resp = await client.get(provider["api_url"], params=params)
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            if resp.status_code != 200:
                return R(
                    success=False,
                    data={"status_code": resp.status_code, "response": resp.text[:500]},
                    message=f"API 返回错误: {resp.status_code}"
                )
            
            raw_data = resp.json()
            
            # 使用字段映射转换数据
            field_mapping = provider.get("field_mapping", {})
            mapped = map_weather_response(raw_data, field_mapping)
            
            return R(success=True, data={
                "raw_response": raw_data,
                "mapped_data": mapped,
                "response_time_ms": response_time_ms,
            })
            
    except httpx.TimeoutException:
        return R(success=False, data=None, message="请求超时")
    except Exception as e:
        return R(success=False, data=None, message=f"请求失败: {str(e)}")


# -------- Admin: AI 配置 --------
@router.get("/admin/ai/config")
async def admin_get_ai_config(db: AsyncSession = Depends(get_db), _=Depends(require_role("admin"))):
    """获取 AI 配置"""
    repo = PlatformRepo(db)
    cfg = await repo.get_or_create_ai_config()
    await db.commit()
    return R(success=True, data={
        "enabled": cfg.enabled,
        "apiUrl": cfg.api_url,
        "apiToken": cfg.api_token,
        "model": cfg.model,
        "temperature": cfg.temperature,
        "maxTokens": cfg.max_tokens,
        "promptTemplate": cfg.prompt_template,
    })


@router.post("/admin/ai/config")
async def admin_set_ai_config(req: AiConfigReq, db: AsyncSession = Depends(get_db), _=Depends(require_role("admin"))):
    """更新 AI 配置"""
    repo = PlatformRepo(db)
    cfg = await repo.update_ai_config(
        enabled=req.enabled,
        api_url=req.apiUrl,
        api_token=req.apiToken,
        model=req.model,
        temperature=req.temperature,
        max_tokens=req.maxTokens,
        prompt_template=req.promptTemplate,
    )
    await db.commit()
    return R(success=True, data={
        "enabled": cfg.enabled,
        "apiUrl": cfg.api_url,
        "apiToken": cfg.api_token,
        "model": cfg.model,
        "temperature": cfg.temperature,
        "maxTokens": cfg.max_tokens,
        "promptTemplate": cfg.prompt_template,
    })


@router.post("/admin/ai/config/test")
async def admin_test_ai_config(db: AsyncSession = Depends(get_db), _=Depends(require_role("admin"))):
    """测试 AI 配置是否可用"""
    import httpx
    
    repo = PlatformRepo(db)
    cfg = await repo.get_or_create_ai_config()
    
    if not cfg.enabled:
        return R(success=False, data=None, message="AI 功能未启用")
    
    if not cfg.api_url or not cfg.api_token:
        return R(success=False, data=None, message="API URL 或 Token 未配置")
    
    # 使用模拟数据测试
    test_prompt = cfg.prompt_template.format(
        studentName="测试学生",
        grades="高等数学: 85分, 大学英语: 90分, 程序设计: 88分",
        averageScore="87.67",
        averageGpa="3.5",
    ) if cfg.prompt_template else "请回复：测试成功"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 兼容 OpenAI 格式的 API
            resp = await client.post(
                cfg.api_url,
                headers={
                    "Authorization": f"Bearer {cfg.api_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": cfg.model or "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": test_prompt}],
                    "temperature": cfg.temperature,
                    "max_tokens": min(cfg.max_tokens, 500),  # 测试时限制 token
                },
            )
            
            if resp.status_code != 200:
                return R(success=False, data={"statusCode": resp.status_code, "response": resp.text[:500]}, message=f"API 返回错误: {resp.status_code}")
            
            result = resp.json()
            # 提取回复内容
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            return R(success=True, data={
                "testPrompt": test_prompt,
                "response": content[:1000],  # 截断过长的响应
                "model": result.get("model", cfg.model),
                "usage": result.get("usage", {}),
            }, message="AI 配置测试成功")
            
    except httpx.TimeoutException:
        return R(success=False, data=None, message="API 请求超时")
    except Exception as e:
        return R(success=False, data=None, message=f"API 请求失败: {str(e)}")


# -------- Admin: 系统监控 --------
@router.get("/admin/system/info")
async def admin_system_info(_=Depends(require_role("admin"))):
    """获取系统基础信息"""
    from .system_service import system_monitor_service
    data = await system_monitor_service.get_system_info()
    return R(success=True, data=data)


@router.get("/admin/system/resources")
async def admin_system_resources(_=Depends(require_role("admin"))):
    """获取当前资源使用率"""
    from .system_service import system_monitor_service
    data = await system_monitor_service.get_resource_usage()
    return R(success=True, data=data)


@router.get("/admin/system/traffic")
async def admin_system_traffic(hours: int = Query(default=24, ge=1), _=Depends(require_role("admin"))):
    """获取网络流量数据"""
    from .system_service import system_monitor_service
    data = await system_monitor_service.get_traffic_data(hours)
    return R(success=True, data=data)


@router.get("/admin/system/cpu-history")
async def admin_system_cpu_history(minutes: int = Query(default=60, ge=1), _=Depends(require_role("admin"))):
    """获取 CPU 使用率历史数据"""
    from .system_service import system_monitor_service
    data = await system_monitor_service.get_cpu_history(minutes)
    return R(success=True, data=data)


# -------- Public: 天气接口（受开关控制，无需登录）--------
@router.get("/weather/current")
async def weather_current(
    request: Request,
    city: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db)
):
    """获取天气数据（公开接口，无需登录）"""
    svc = WeatherSwitchService(db)
    sw = await svc.get_switch()
    if not sw["enabled"]:
        raise HTTPException(status_code=503, detail="Weather API disabled by admin")

    # 使用全局共享的 HTTP 客户端（与 /api/weather 保持一致）
    from app.clients.weather_client import OpenWeatherClient, BackupWeatherClient
    
    http_client = request.app.state.http_client
    openweather_client = OpenWeatherClient(http_client)
    backup_client = BackupWeatherClient(http_client)
    ws = weather_service.WeatherService(openweather_client, backup_client, db)
    result = await ws.get_weather_by_city(city)
    return R(success=result.success, data=result.data, message=result.message)


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
    """获取学生可用的 AI 提示词（包括管理员配置的默认模板）"""
    repo = PlatformRepo(db)
    
    # 获取 ai_prompt_template 表中的提示词
    ps = await repo.get_prompts(role="student")
    data = [{"id": str(p.id), "name": p.name, "content": p.content} for p in ps]
    
    # 获取管理员在 ai_config 中配置的默认提示词模板
    cfg = await repo.get_or_create_ai_config()
    if cfg.prompt_template and cfg.prompt_template.strip():
        # 将管理员配置的模板作为默认选项添加到列表开头
        data.insert(0, {
            "id": "default",
            "name": "默认分析模板",
            "content": cfg.prompt_template
        })
    
    return R(success=True, data=data)


@router.get("/student/ai/history")
async def student_ai_history(
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    u=Depends(require_role("student"))
):
    """获取学生的 AI 分析历史"""
    repo = PlatformRepo(db)
    items, total = await repo.get_analysis_history(u.id, page=page, page_size=pageSize)
    data = [
        {
            "id": str(h.id),
            "semester": h.semester,
            "promptName": h.prompt_name,
            "outputText": h.output_text,
            "createdAt": h.created_at.isoformat() if h.created_at else None,
        }
        for h in items
    ]
    return R(success=True, data={"items": data, "total": total, "page": page, "pageSize": pageSize})


@router.delete("/student/ai/history/{history_id}")
async def student_delete_ai_history(
    history_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    u=Depends(require_role("student"))
):
    """删除学生的 AI 分析历史记录"""
    repo = PlatformRepo(db)
    deleted = await repo.delete_analysis_history(u.id, history_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="记录不存在或无权删除")
    await db.commit()
    return R(success=True, data={"id": str(history_id)}, message="删除成功")


@router.post("/student/ai/analyze")
async def student_ai_analyze(req: AnalyzeReq, db: AsyncSession = Depends(get_db), u=Depends(require_role("student"))):
    repo = PlatformRepo(db)
    prompt_name = "默认分析"
    prompt_text = req.extra_prompt or ""

    if req.prompt_id:
        # 处理 "default" 特殊 ID（管理员配置的默认模板）
        if req.prompt_id == "default":
            cfg = await repo.get_or_create_ai_config()
            if cfg.prompt_template and cfg.prompt_template.strip():
                prompt_name = "默认分析模板"
                prompt_text = cfg.prompt_template + ("\n" + prompt_text if prompt_text else "")
        else:
            # 尝试从 ai_prompt_template 表获取
            try:
                p = await repo.get_prompt_by_id(uuid.UUID(req.prompt_id))
                if p:
                    prompt_name = p.name
                    prompt_text = (p.content or "") + ("\n" + prompt_text if prompt_text else "")
            except ValueError:
                # 无效的 UUID 格式，忽略
                pass

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
