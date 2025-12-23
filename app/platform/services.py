from datetime import datetime, timedelta, timezone
import uuid
import math
import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from .repo import PlatformRepo
from .security import (
    hash_password,
    verify_password,
    verify_password_async,
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

logger = logging.getLogger(__name__)


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
        if not u.password_hash or not await verify_password_async(password, u.password_hash):
            return {"ok": False, "msg": "密码错误"}

        access = create_access_token(subject=str(u.id), role="admin")
        refresh = create_refresh_token()

        r = await get_redis()
        await r.setex(f"auth:refresh:{refresh}", int(timedelta(days=platform_settings.refresh_token_days).total_seconds()), str(u.id))

        exp = datetime.now() + timedelta(minutes=platform_settings.access_token_minutes)
        # 返回毫秒时间戳，前端更容易处理
        expires_ms = int(exp.timestamp() * 1000)
        return {
            "ok": True,
            "data": {
                "username": u.username,
                "roles": ["admin"],
                "accessToken": access,
                "refreshToken": refresh,
                "expires": expires_ms,
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

        # AcademicService.login() 返回 {"success": True, "data": {"sessionId": ...}}
        lr_data = lr.get("data") or {}
        session_id = lr_data.get("sessionId") or lr_data.get("session_id") or lr.get("session_id") or lr.get("sessionId")
        if not session_id:
            # 兜底：如果你 AcademicService 的返回字段不同，改这里
            return {"ok": False, "msg": "教务登录成功但未返回 session_id（请对齐 AcademicService 返回值）"}

        # 2) 若平台用户不存在：按策略创建/拒绝
        if not u:
            if not platform_settings.student_auto_provision:
                return {"ok": False, "msg": "该学生未被管理员批准开通"}
            u = await self.repo.create_user(username=username, role="student", student_id=username, password_hash=None)
            await self.db.commit()  # 提交新用户到数据库

        # 3) 把教务 session 放 redis（不存密码）
        r = await get_redis()
        await r.setex(f"acad:sess:{u.id}", 8 * 3600, session_id)  # 8h

        # 4) 发 JWT
        access = create_access_token(subject=str(u.id), role="student")
        refresh = create_refresh_token()
        await r.setex(f"auth:refresh:{refresh}", int(timedelta(days=platform_settings.refresh_token_days).total_seconds()), str(u.id))

        exp = datetime.now() + timedelta(minutes=platform_settings.access_token_minutes)
        # 返回毫秒时间戳，前端更容易处理
        expires_ms = int(exp.timestamp() * 1000)
        return {
            "ok": True,
            "data": {
                "username": u.username,
                "roles": ["student"],
                "accessToken": access,
                "refreshToken": refresh,
                "expires": expires_ms,
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


def _to_float(x) -> float | None:
    """解析数值，支持字符串和数字"""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    try:
        return float(str(x).strip())
    except Exception:
        return None


def _is_passed(score_str: str | None) -> bool:
    """
    判断成绩是否及格
    支持等级制和百分制成绩
    """
    if not score_str:
        return False
    
    score = str(score_str).strip()
    
    # 处理等级制成绩 - 及格
    passed_grades = {'优', '优秀', '良', '良好', '中', '中等', '及格', '合格', '通过'}
    if score in passed_grades:
        return True
    
    # 处理等级制成绩 - 不及格
    failed_grades = {'不及格', '不合格', '差', '未通过', '缺考', '作弊', '取消'}
    if score in failed_grades:
        return False
    
    # 处理百分制成绩
    try:
        num_score = float(score)
        return num_score >= 60
    except (ValueError, TypeError):
        pass
    
    # 无法判断时默认及格
    return True


def _basic_grade_stats(rows: list[dict]) -> dict:
    """
    计算成绩统计信息（参考前端 SemesterGrades 模型）
    
    统计逻辑：
    - averageScore: 加权平均分 = sum(score * credit) / sum(credit)
    - averageGpa: 加权平均绩点 = sum(gpa * credit) / sum(credit)
    - earnedCredits: 及格课程的学分之和
    
    Args:
        rows: 成绩数据列表
        
    Returns:
        包含统计信息的字典
    """
    # 字段名映射
    score_keys = ["成绩", "总评", "最终", "分数", "总成绩", "课程成绩"]
    name_keys = ["课程名称", "课程", "课程名", "名称"]
    credit_keys = ["学分", "课程学分"]
    gpa_keys = ["绩点", "GPA"]

    items = []
    
    # 统计变量
    total_score_points = 0.0  # 分数 * 学分
    total_score_credits = 0.0  # 有分数的课程学分
    total_gpa_points = 0.0  # 绩点 * 学分
    total_gpa_credits = 0.0  # 有绩点的课程学分
    earned_credits = 0.0  # 及格课程学分
    
    for r in rows:
        # 解析课程名
        course = ""
        for nk in name_keys:
            if nk in r and r[nk]:
                course = str(r[nk]).strip()
                break
        
        # 解析成绩
        score_str = None
        score = None
        for k in score_keys:
            if k in r and r[k]:
                score_str = str(r[k]).strip()
                score = _to_float(r[k])
                break
        
        # 解析学分
        credit = 0.0
        for ck in credit_keys:
            if ck in r and r[ck]:
                credit = _to_float(r[ck]) or 0.0
                break
        
        # 解析绩点
        gpa = None
        for gk in gpa_keys:
            if gk in r and r[gk]:
                gpa = _to_float(r[gk])
                break
        
        # 判断是否及格
        is_passed = _is_passed(score_str)
        
        items.append({
            "course": course or "未知课程",
            "score": score,
            "score_str": score_str,
            "credit": credit,
            "gpa": gpa,
            "isPassed": is_passed,
        })
        
        # 统计加权平均分（只计算有数字成绩的课程）
        if score is not None and credit > 0:
            total_score_points += score * credit
            total_score_credits += credit
        
        # 统计加权平均绩点（只计算有绩点的课程）
        if gpa is not None and credit > 0:
            total_gpa_points += gpa * credit
            total_gpa_credits += credit
        
        # 统计已获学分（及格的课程）
        if is_passed and credit > 0:
            earned_credits += credit

    if not items:
        return {
            "count": 0,
            "avg": None,
            "avgGpa": None,
            "earnedCredits": 0,
            "top": [],
            "bottom": [],
            "dist": {},
            "items": [],
        }

    # 计算加权平均分
    avg_score = round(total_score_points / total_score_credits, 2) if total_score_credits > 0 else None
    
    # 计算加权平均绩点
    avg_gpa = round(total_gpa_points / total_gpa_credits, 2) if total_gpa_credits > 0 else None

    # 排序（只对有数字成绩的课程排序）
    items_with_score = [i for i in items if i["score"] is not None]
    top = sorted(items_with_score, key=lambda x: x["score"], reverse=True)[:5]
    bottom = sorted(items_with_score, key=lambda x: x["score"])[:5]

    # 成绩分布
    def bucket(s: float) -> str:
        if s >= 90:
            return "90+"
        if s >= 80:
            return "80-89"
        if s >= 70:
            return "70-79"
        if s >= 60:
            return "60-69"
        return "<60"

    dist = {}
    for i in items_with_score:
        b = bucket(i["score"])
        dist[b] = dist.get(b, 0) + 1

    return {
        "count": len(items),
        "avg": avg_score,
        "avgGpa": avg_gpa,
        "earnedCredits": round(earned_credits, 1),
        "top": top,
        "bottom": bottom,
        "dist": dist,
        "items": items,
    }


def _format_grades_for_prompt(items: list[dict]) -> str:
    """
    将成绩数据格式化为适合 prompt 的文本
    
    Args:
        items: 课程成绩列表
        
    Returns:
        格式化后的成绩文本
    """
    if not items:
        return "暂无成绩数据"
    
    lines = []
    for item in items:
        course = item.get("course", "未知课程")
        score = item.get("score_str") or item.get("score")
        credit = item.get("credit", 0)
        gpa = item.get("gpa")
        
        # 格式化输出
        if gpa is not None:
            lines.append(f"- {course}: {score}分, {credit}学分, 绩点{gpa}")
        else:
            lines.append(f"- {course}: {score}分, {credit}学分")
    return "\n".join(lines)


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

    async def _get_student_name(self) -> str:
        """获取学生姓名"""
        try:
            profile = await self.get_profile()
            if profile.get("ok") and profile.get("data"):
                data = profile["data"].get("data", {})
                return data.get("name", "") or data.get("姓名", "") or "同学"
        except Exception:
            pass
        return "同学"

    async def _call_ai_api(self, prompt: str) -> str | None:
        """
        调用 AI API 进行分析
        
        Args:
            prompt: 完整的提示词（已替换占位符）
            
        Returns:
            AI 返回的分析结果，失败返回 None
        """
        cfg = await self.repo.get_or_create_ai_config()
        
        # 检查 AI 是否启用
        if not cfg.enabled:
            logger.info("AI 功能未启用，跳过 AI 分析")
            return None
        
        if not cfg.api_url or not cfg.api_token:
            logger.warning("AI API URL 或 Token 未配置")
            return None
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    cfg.api_url,
                    headers={
                        "Authorization": f"Bearer {cfg.api_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": cfg.model or "gpt-3.5-turbo",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": cfg.temperature,
                        "max_tokens": cfg.max_tokens,
                    },
                )
                
                if resp.status_code != 200:
                    logger.error(f"AI API 返回错误: {resp.status_code} - {resp.text[:500]}")
                    return None
                
                result = resp.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                return content if content else None
                
        except httpx.TimeoutException:
            logger.error("AI API 请求超时")
            return None
        except Exception as e:
            logger.error(f"AI API 请求失败: {str(e)}")
            return None

    async def _build_ai_prompt(self, *, prompt_template: str, stats: dict, student_name: str) -> str:
        """
        构建 AI 分析的完整 prompt
        
        Args:
            prompt_template: prompt 模板（包含占位符）
            stats: 成绩统计信息
            student_name: 学生姓名
            
        Returns:
            替换占位符后的完整 prompt
        """
        # 格式化成绩明细
        grades_text = _format_grades_for_prompt(stats.get("items", []))
        
        # 获取平均分和平均绩点
        avg_score = stats.get("avg")
        avg_gpa = stats.get("avgGpa")
        
        # 替换模板中的占位符
        prompt = prompt_template.format(
            studentName=student_name,
            averageScore=avg_score if avg_score is not None else "N/A",
            averageGpa=avg_gpa if avg_gpa is not None else "N/A",
            grades=grades_text,
        )
        
        return prompt

    def _build_local_analysis(self, *, semester: str, stats: dict, extra_prompt: str = "") -> str:
        """
        构建本地分析结果（不调用 AI 时的备用方案）
        
        Args:
            semester: 学期
            stats: 成绩统计信息
            extra_prompt: 额外的分析侧重点
            
        Returns:
            本地分析结果文本
        """
        lines = []
        lines.append(f"分析时间：{_now_str()}")
        lines.append(f"学期：{semester or '全部'}")
        
        # 统计信息
        avg_score = stats.get("avg")
        avg_gpa = stats.get("avgGpa")
        earned_credits = stats.get("earnedCredits", 0)
        
        lines.append(f"统计：课程数={stats.get('count')} 平均分={avg_score} 平均绩点={avg_gpa} 已获学分={earned_credits}")
        lines.append(f"分布：{stats.get('dist')}")
        
        lines.append("Top 5：")
        for i in stats.get("top", []):
            lines.append(f"- {i['course']}：{i.get('score_str') or i.get('score')}分")
        lines.append("Bottom 5：")
        for i in stats.get("bottom", []):
            lines.append(f"- {i['course']}：{i.get('score_str') or i.get('score')}分")

        # 给一些通用建议
        lines.append("\n【建议】")
        if avg_score is not None and avg_score < 75:
            lines.append("- 先把「低分课」拉到 70+：提分性价比最高。")
        lines.append("- 把 Bottom 课程按知识点拆分成清单，每周固定复盘。")
        lines.append("- 对 Top 课程总结「有效学习方法」，迁移到弱项。")

        return "\n".join(lines)

    async def analyze_grades(self, *, semester: str, prompt_text: str, rows: list[dict]) -> str:
        """
        分析成绩（优先调用 AI，失败时使用本地分析）
        
        Args:
            semester: 学期
            prompt_text: prompt 模板或额外提示
            rows: 成绩数据
            
        Returns:
            分析结果文本
        """
        stats = _basic_grade_stats(rows)
        
        # 如果有 prompt 模板且包含占位符，尝试调用 AI
        if prompt_text and "{" in prompt_text and "}" in prompt_text:
            try:
                student_name = await self._get_student_name()
                full_prompt = await self._build_ai_prompt(
                    prompt_template=prompt_text,
                    stats=stats,
                    student_name=student_name,
                )
                
                # 调用 AI API
                ai_result = await self._call_ai_api(full_prompt)
                if ai_result:
                    return ai_result
                    
            except Exception as e:
                logger.error(f"AI 分析失败: {str(e)}")
        
        # AI 分析失败或未配置，使用本地分析
        return self._build_local_analysis(semester=semester, stats=stats, extra_prompt=prompt_text)

    async def ai_analyze(self, *, semester: str, prompt_name: str, prompt_text: str, grades_payload: dict) -> str:
        """
        执行 AI 成绩分析并保存历史
        
        Args:
            semester: 学期
            prompt_name: 提示词名称
            prompt_text: 提示词内容
            grades_payload: 成绩数据
            
        Returns:
            分析结果文本
        """
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
