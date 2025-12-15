from datetime import datetime, timedelta, timezone
import uuid
import math

from sqlalchemy.ext.asyncio import AsyncSession

from .repo import PlatformRepo
from .security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
)
from .redis_client import get_redis, redis_set_json, redis_get_json
from .settings import platform_settings
from .models import AiAnalysisHistory

# 这里复用你已有的教务 service（你项目里已有 semesters/grades/me/schedule 接口就更好）
# 如果你的路径不叫 app.services.academic_service，改下面导入即可
try:
    from app.services.academic_service import AcademicService  # type: ignore
except Exception:  # pragma: no cover
    AcademicService = None  # type: ignore


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = PlatformRepo(db)

    async def login_admin(self, username: str, password: str) -> dict:
        u = await self.repo.get_user_by_username(username)
        if not u or u.role != "admin":
            return {"ok": False, "msg": "管理员账号不存在"}
        if not u.is_enabled:
            return {"ok": False, "msg": "该管理员已被禁用"}
        if not u.password_hash or not verify_password(password, u.password_hash):
            return {"ok": False, "msg": "密码错误"}

        access = create_access_token(subject=str(u.id), role="admin")
        refresh = create_refresh_token()

        r = await get_redis()
        await r.setex(f"auth:refresh:{refresh}", int(timedelta(days=platform_settings.refresh_token_days).total_seconds()), str(u.id))

        exp = datetime.now() + timedelta(minutes=platform_settings.access_token_minutes)
        return {
            "ok": True,
            "data": {
                "username": u.username,
                "roles": ["admin"],
                "accessToken": access,
                "refreshToken": refresh,
                "expires": exp.strftime("%Y/%m/%d %H:%M:%S"),
            },
        }

    async def login_student(self, username: str, password: str) -> dict:
        # username 推荐直接学号
        u = await self.repo.get_user_by_username(username)
        if u and u.role != "student":
            return {"ok": False, "msg": "该账号不是学生账号"}
        if u and not u.is_enabled:
            return {"ok": False, "msg": "该学生已被管理员禁止登录"}

        if AcademicService is None:
            return {"ok": False, "msg": "后端缺少 AcademicService（请检查导入路径）"}

        # 1) 先用教务系统校验账号密码 + 拿 session（你现有 AcademicService.login 已打通）
        acad = AcademicService(self.db)
        lr = await acad.login(username=username, password=password, request_id=None)
        if not lr.get("success"):
            return {"ok": False, "msg": "教务系统登录失败（账号或密码错误/验证码/站点异常）"}

        session_id = lr.get("session_id") or lr.get("sessionId") or lr.get("id")
        if not session_id:
            # 兜底：如果你 AcademicService 的返回字段不同，改这里
            return {"ok": False, "msg": "教务登录成功但未返回 session_id（请对齐 AcademicService 返回值）"}

        # 2) 若平台用户不存在：按策略创建/拒绝
        if not u:
            if not platform_settings.student_auto_provision:
                return {"ok": False, "msg": "该学生未被管理员批准开通"}
            u = await self.repo.create_user(username=username, role="student", student_id=username, password_hash=None)

        # 3) 把教务 session 放 redis（不存密码）
        r = await get_redis()
        await r.setex(f"acad:sess:{u.id}", 8 * 3600, session_id)  # 8h

        # 4) 发 JWT
        access = create_access_token(subject=str(u.id), role="student")
        refresh = create_refresh_token()
        await r.setex(f"auth:refresh:{refresh}", int(timedelta(days=platform_settings.refresh_token_days).total_seconds()), str(u.id))

        exp = datetime.now() + timedelta(minutes=platform_settings.access_token_minutes)
        return {
            "ok": True,
            "data": {
                "username": u.username,
                "roles": ["student"],
                "accessToken": access,
                "refreshToken": refresh,
                "expires": exp.strftime("%Y/%m/%d %H:%M:%S"),
            },
        }


class WeatherSwitchService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = PlatformRepo(db)

    async def get_switch(self) -> dict:
        ws = await self.repo.get_or_create_weather_switch(platform_settings.weather_enabled_default)
        await redis_set_json("weather:enabled", {"enabled": ws.enabled}, ttl_seconds=3600)
        return {"enabled": ws.enabled}

    async def set_switch(self, enabled: bool) -> dict:
        ws = await self.repo.get_or_create_weather_switch(platform_settings.weather_enabled_default)
        ws.enabled = enabled
        await self.db.flush()
        await redis_set_json("weather:enabled", {"enabled": ws.enabled}, ttl_seconds=3600)
        return {"enabled": ws.enabled}

    async def set_backup_payload(self, payload: dict) -> None:
        ws = await self.repo.get_or_create_weather_switch(platform_settings.weather_enabled_default)
        ws.last_backup_json = payload
        await self.db.flush()

    async def get_backup_payload(self) -> dict | None:
        ws = await self.repo.get_or_create_weather_switch(platform_settings.weather_enabled_default)
        return ws.last_backup_json


def _to_float(x: str) -> float | None:
    try:
        return float(str(x).strip())
    except Exception:
        return None


def _basic_grade_stats(rows: list[dict]) -> dict:
    # 尽量兼容：你 grades rows 里可能用 “成绩/总评/最终”等字段名
    score_keys = ["成绩", "总评", "最终", "分数", "总成绩", "课程成绩"]
    name_keys = ["课程名称", "课程", "课程名", "名称"]

    items = []
    for r in rows:
        score = None
        for k in score_keys:
            if k in r and r[k]:
                score = _to_float(r[k])
                break
        course = ""
        for nk in name_keys:
            if nk in r and r[nk]:
                course = str(r[nk]).strip()
                break
        if score is not None:
            items.append({"course": course or "未知课程", "score": score})

    if not items:
        return {"count": 0, "avg": None, "top": [], "bottom": [], "dist": {}}

    scores = [i["score"] for i in items]
    avg = sum(scores) / len(scores)
    var = sum((s - avg) ** 2 for s in scores) / len(scores)
    std = math.sqrt(var)

    top = sorted(items, key=lambda x: x["score"], reverse=True)[:5]
    bottom = sorted(items, key=lambda x: x["score"])[:5]

    def bucket(s: float) -> str:
        if s >= 90: return "90+"
        if s >= 80: return "80-89"
        if s >= 70: return "70-79"
        if s >= 60: return "60-69"
        return "<60"

    dist = {}
    for s in scores:
        b = bucket(s)
        dist[b] = dist.get(b, 0) + 1

    return {
        "count": len(items),
        "avg": round(avg, 2),
        "std": round(std, 2),
        "top": top,
        "bottom": bottom,
        "dist": dist,
    }


class StudentService:
    def __init__(self, db: AsyncSession, user_id: uuid.UUID):
        self.db = db
        self.user_id = user_id
        self.repo = PlatformRepo(db)

    async def _get_acad_session_id(self) -> str | None:
        r = await get_redis()
        return await r.get(f"acad:sess:{self.user_id}")

    async def get_profile(self) -> dict:
        sess = await self._get_acad_session_id()
        if not sess:
            return {"ok": False, "msg": "教务会话已过期，请重新登录"}

        acad = AcademicService(self.db)
        data = await acad.me(session_id=sess, request_id=None)
        return {"ok": bool(data.get("success")), "data": data}

    async def get_semesters(self) -> dict:
        sess = await self._get_acad_session_id()
        if not sess:
            return {"ok": False, "msg": "教务会话已过期，请重新登录"}
        acad = AcademicService(self.db)
        data = await acad.semesters(session_id=sess, request_id=None)
        return {"ok": bool(data.get("success")), "data": data}

    async def get_grades(self, semester: str) -> dict:
        sess = await self._get_acad_session_id()
        if not sess:
            return {"ok": False, "msg": "教务会话已过期，请重新登录"}
        acad = AcademicService(self.db)
        data = await acad.grades(session_id=sess, semester=semester, request_id=None)
        return {"ok": bool(data.get("success")), "data": data}

    async def get_schedule(self, xnxq: str = "") -> dict:
        sess = await self._get_acad_session_id()
        if not sess:
            return {"ok": False, "msg": "教务会话已过期，请重新登录"}
        acad = AcademicService(self.db)
        data = await acad.schedule(session_id=sess, xnxq=xnxq, request_id=None)
        return {"ok": bool(data.get("success")), "data": data}

    async def analyze_grades(self, *, semester: str, prompt_text: str, rows: list[dict]) -> str:
        stats = _basic_grade_stats(rows)
        # 这里先做“可解释”的本地分析（不依赖外部模型），你后续再接大模型也不伤结构
        lines = []
        lines.append(f"分析时间：{_now_str()}")
        lines.append(f"学期：{semester or '全部'}")
        lines.append(f"统计：课程数={stats.get('count')} 平均分={stats.get('avg')} 标准差={stats.get('std')}")
        lines.append(f"分布：{stats.get('dist')}")
        lines.append("Top 5：")
        for i in stats.get("top", []):
            lines.append(f"- {i['course']}：{i['score']}")
        lines.append("Bottom 5：")
        for i in stats.get("bottom", []):
            lines.append(f"- {i['course']}：{i['score']}")

        # prompt_text 作为“分析侧重点”提示
        if prompt_text.strip():
            lines.append("\n【你的分析侧重点】")
            lines.append(prompt_text.strip())

        # 给一些通用建议
        lines.append("\n【建议】")
        if stats.get("avg") is not None and stats["avg"] < 75:
            lines.append("- 先把“低分课”拉到 70+：提分性价比最高。")
        lines.append("- 把 Bottom 课程按知识点拆分成清单，每周固定复盘。")
        lines.append("- 对 Top 课程总结“有效学习方法”，迁移到弱项。")

        return "\n".join(lines)

    async def ai_analyze(self, *, semester: str, prompt_name: str, prompt_text: str, grades_payload: dict) -> str:
        rows = grades_payload.get("rows") or []
        out = await self.analyze_grades(semester=semester, prompt_text=prompt_text, rows=rows)

        # 存历史
        hist = AiAnalysisHistory(
            user_id=self.user_id,
            semester=semester or "",
            prompt_name=prompt_name,
            input_json={"semester": semester, "rows_count": len(rows)},
            output_text=out,
        )
        await self.repo.add_analysis(hist)
        return out
