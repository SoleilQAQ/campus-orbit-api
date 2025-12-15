from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import PlatformUser, WeatherSwitch, AiPromptTemplate, AiAnalysisHistory, AiConfig


class PlatformRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_by_username(self, username: str) -> PlatformUser | None:
        q = await self.db.execute(select(PlatformUser).where(PlatformUser.username == username))
        return q.scalar_one_or_none()

    async def create_user(self, *, username: str, role: str, student_id: str | None, password_hash: str | None) -> PlatformUser:
        u = PlatformUser(username=username, role=role, student_id=student_id, password_hash=password_hash, is_enabled=True)
        self.db.add(u)
        await self.db.flush()
        return u

    async def list_users(self, role: str | None = None) -> list[PlatformUser]:
        stmt = select(PlatformUser).order_by(PlatformUser.created_at.desc())
        if role:
            stmt = stmt.where(PlatformUser.role == role)
        q = await self.db.execute(stmt)
        return list(q.scalars().all())

    async def set_user_enabled(self, user_id, enabled: bool) -> None:
        u = await self.db.get(PlatformUser, user_id)
        if not u:
            return
        u.is_enabled = enabled
        await self.db.flush()

    async def get_or_create_weather_switch(self, enabled_default: bool) -> WeatherSwitch:
        q = await self.db.execute(select(WeatherSwitch).limit(1))
        ws = q.scalar_one_or_none()
        if ws:
            return ws
        ws = WeatherSwitch(enabled=enabled_default)
        self.db.add(ws)
        await self.db.flush()
        return ws

    async def get_prompts(self, role: str = "student") -> list[AiPromptTemplate]:
        q = await self.db.execute(
            select(AiPromptTemplate).where(AiPromptTemplate.role == role, AiPromptTemplate.is_enabled == True)  # noqa
        )
        return list(q.scalars().all())

    async def get_prompt_by_id(self, pid) -> AiPromptTemplate | None:
        return await self.db.get(AiPromptTemplate, pid)

    async def add_analysis(self, hist: AiAnalysisHistory) -> None:
        self.db.add(hist)
        await self.db.flush()

    async def get_analysis_history(self, user_id, page: int = 1, page_size: int = 10) -> tuple[list[AiAnalysisHistory], int]:
        """获取用户的 AI 分析历史（分页）"""
        from sqlalchemy import func
        
        # 获取总数
        count_q = await self.db.execute(
            select(func.count()).select_from(AiAnalysisHistory).where(AiAnalysisHistory.user_id == user_id)
        )
        total = count_q.scalar() or 0
        
        # 获取分页数据
        offset = (page - 1) * page_size
        q = await self.db.execute(
            select(AiAnalysisHistory)
            .where(AiAnalysisHistory.user_id == user_id)
            .order_by(AiAnalysisHistory.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list(q.scalars().all())
        return items, total

    async def delete_analysis_history(self, user_id, history_id) -> bool:
        """删除用户的 AI 分析历史记录（只能删除自己的）"""
        hist = await self.db.get(AiAnalysisHistory, history_id)
        if not hist or hist.user_id != user_id:
            return False
        await self.db.delete(hist)
        await self.db.flush()
        return True

    async def get_or_create_ai_config(self) -> AiConfig:
        """获取或创建 AI 配置（全局单例）"""
        q = await self.db.execute(select(AiConfig).limit(1))
        cfg = q.scalar_one_or_none()
        if cfg:
            return cfg
        # 创建默认配置
        cfg = AiConfig(
            enabled=False,
            api_url="",
            api_token="",
            model="",
            temperature=0.7,
            max_tokens=2000,
            prompt_template="",
        )
        self.db.add(cfg)
        await self.db.flush()
        return cfg

    async def update_ai_config(
        self,
        *,
        enabled: bool,
        api_url: str,
        api_token: str,
        model: str,
        temperature: float,
        max_tokens: int,
        prompt_template: str,
    ) -> AiConfig:
        """更新 AI 配置"""
        cfg = await self.get_or_create_ai_config()
        cfg.enabled = enabled
        cfg.api_url = api_url
        cfg.api_token = api_token
        cfg.model = model
        cfg.temperature = temperature
        cfg.max_tokens = max_tokens
        cfg.prompt_template = prompt_template
        await self.db.flush()
        return cfg

    async def search_students(self, keyword: str) -> dict:
        """
        根据关键字精确查找学生信息（从 academic_user 表）
        优先按学号精确匹配，其次按姓名精确匹配
        
        Args:
            keyword: 搜索关键字（学号或姓名）
            
        Returns:
            包含匹配结果的字典：
            - 如果只有一个匹配：返回完整的 StudentDetailInfo
            - 如果有多个同名：返回候选列表供用户选择
            - 如果没有匹配：返回空结果
        """
        from app.models.academic_models import AcademicUser, AcademicGrade
        from sqlalchemy import or_
        
        # 1. 首先尝试按学号精确匹配
        stmt = select(AcademicUser).where(AcademicUser.student_id == keyword)
        q = await self.db.execute(stmt)
        user = q.scalar_one_or_none()
        
        if user:
            # 学号精确匹配，返回单个学生的详细信息
            detail = await self._build_student_detail(user)
            return {
                "matchType": "exact",  # 精确匹配
                "count": 1,
                "data": detail,
                "candidates": None,
            }
        
        # 2. 按姓名精确匹配
        stmt = select(AcademicUser).where(AcademicUser.name == keyword).order_by(AcademicUser.student_id)
        q = await self.db.execute(stmt)
        users = list(q.scalars().all())
        
        if len(users) == 1:
            # 只有一个同名学生，返回详细信息
            detail = await self._build_student_detail(users[0])
            return {
                "matchType": "exact",
                "count": 1,
                "data": detail,
                "candidates": None,
            }
        elif len(users) > 1:
            # 存在同名学生，返回候选列表供用户选择
            candidates = []
            for u in users:
                platform_user = await self.get_user_by_username(u.student_id)
                candidates.append({
                    "studentId": u.student_id,
                    "name": u.name,
                    "className": u.class_name,
                    "major": u.major,
                    "grade": u.enrollment_year,
                    "college": u.college,
                    "isRegistered": platform_user is not None,
                })
            return {
                "matchType": "multiple",  # 多个匹配（同名）
                "count": len(users),
                "data": None,
                "candidates": candidates,
            }
        
        # 3. 没有精确匹配，返回空结果
        return {
            "matchType": "none",  # 无匹配
            "count": 0,
            "data": None,
            "candidates": None,
        }

    def _is_passed(self, score_str: str | None) -> bool:
        """
        判断成绩是否及格
        支持等级制和百分制成绩
        
        Args:
            score_str: 成绩字符串
            
        Returns:
            是否及格
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

    def _parse_credit(self, credit_value) -> float:
        """
        解析学分值，支持多种格式
        
        Args:
            credit_value: 学分值（可能是字符串、数字或None）
            
        Returns:
            学分浮点数
        """
        if credit_value is None:
            return 0.0
        
        # 如果已经是数字
        if isinstance(credit_value, (int, float)):
            return float(credit_value)
        
        # 字符串处理
        credit_str = str(credit_value).strip()
        if not credit_str:
            return 0.0
        
        try:
            return float(credit_str)
        except (ValueError, TypeError):
            return 0.0

    def _parse_gpa(self, gpa_value) -> float | None:
        """
        解析绩点值
        
        Args:
            gpa_value: 绩点值
            
        Returns:
            绩点浮点数或None
        """
        if gpa_value is None:
            return None
        
        if isinstance(gpa_value, (int, float)):
            return float(gpa_value)
        
        gpa_str = str(gpa_value).strip()
        if not gpa_str:
            return None
        
        try:
            return float(gpa_str)
        except (ValueError, TypeError):
            return None

    async def _build_student_detail(self, user) -> dict:
        """
        构建单个学生的详细信息（StudentDetailInfo 格式）
        
        统计逻辑：
        - totalCredits: 已获学分（每门课只算一次，有及格记录才算）
        - averageGpa: 加权平均绩点
        - totalCourses: 不重复的课程数
        
        Args:
            user: AcademicUser 对象
            
        Returns:
            StudentDetailInfo 格式的字典
        """
        from app.models.academic_models import AcademicGrade
        
        # 查询该学生在平台的登录状态
        platform_user = await self.get_user_by_username(user.student_id)
        
        # 查询该学生的成绩（按学期降序、课程名排序）
        grades_stmt = select(AcademicGrade).where(
            AcademicGrade.student_id == user.student_id
        ).order_by(AcademicGrade.semester.desc(), AcademicGrade.course_name)
        grades_q = await self.db.execute(grades_stmt)
        grades = list(grades_q.scalars().all())
        
        # 构建成绩列表
        grades_list = []
        
        # 用于统计的字典：按课程名统计，每门课只计算一次
        # {课程名: (学分, 是否有及格记录)}
        course_stats = {}
        
        # 绩点统计
        total_gpa_points = 0.0
        valid_gpa_credits = 0.0
        
        for g in grades:
            # 解析学分
            credit = self._parse_credit(g.credit)
            if credit == 0.0 and g.raw_json:
                raw_credit = g.raw_json.get("学分") or g.raw_json.get("课程学分")
                if raw_credit:
                    credit = self._parse_credit(raw_credit)
            
            # 解析绩点
            gpa = self._parse_gpa(g.gpa)
            if gpa is None and g.raw_json:
                raw_gpa = g.raw_json.get("绩点") or g.raw_json.get("GPA")
                if raw_gpa:
                    gpa = self._parse_gpa(raw_gpa)
            
            # 成绩字符串
            score_str = g.score or ""
            if not score_str and g.raw_json:
                score_str = g.raw_json.get("成绩") or g.raw_json.get("总评成绩") or ""
            
            # 判断是否及格
            is_passed = self._is_passed(score_str)
            
            # 添加到成绩列表（所有记录都返回）
            grades_list.append({
                "courseCode": g.course_code,
                "courseName": g.course_name,
                "credit": credit,
                "score": score_str,
                "gpa": gpa,
                "semester": g.semester,
                "isPassed": is_passed,
            })
            
            # 统计课程（每门课只记录一次，有及格就标记为及格）
            course_name = g.course_name or ""
            if course_name:
                if course_name not in course_stats:
                    course_stats[course_name] = (credit, is_passed)
                else:
                    old_credit, old_passed = course_stats[course_name]
                    # 如果之前没及格，现在及格了，更新状态
                    if not old_passed and is_passed:
                        course_stats[course_name] = (credit, True)
            
            # 绩点统计（所有有绩点的记录都参与）
            if gpa is not None and credit > 0:
                total_gpa_points += gpa * credit
                valid_gpa_credits += credit
        
        # 计算已获学分（每门课只算一次，有及格记录才算）
        earned_credits = sum(
            credit for credit, passed in course_stats.values() if passed and credit > 0
        )
        
        # 计算平均绩点
        average_gpa = round(total_gpa_points / valid_gpa_credits, 2) if valid_gpa_credits > 0 else 0.0
        
        # 课程数量 = 不重复的课程数
        total_courses = len(course_stats)
        
        return {
            "student": {
                "studentId": user.student_id,
                "name": user.name,
                "className": user.class_name,
                "major": user.major,
                "grade": user.enrollment_year,
                "college": user.college,
                "isEnabled": platform_user.is_enabled if platform_user else None,
                "isRegistered": platform_user is not None,
            },
            "grades": grades_list,
            "statistics": {
                "totalCredits": round(earned_credits, 1),  # 已获学分
                "averageGpa": average_gpa,
                "totalCourses": total_courses,  # 不重复的课程数
            },
        }
