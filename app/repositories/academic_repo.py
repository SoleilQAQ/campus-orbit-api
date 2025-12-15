from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.models.academic_models import (
    AcademicUser,
    AcademicSnapshot,
    AcademicGrade,
    AcademicSchedule,
    AcademicScheduleCourse,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _truncate_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    # 防止 snapshot/data 写入超大 html_sample 把库撑爆
    if isinstance(payload, dict) and "html_sample" in payload and isinstance(payload["html_sample"], str):
        payload = dict(payload)
        payload["html_sample"] = payload["html_sample"][:500]
    return payload


class AcademicRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.redis = get_redis()

    # ========= Redis Keys =========
    def _k_me(self, student_id: str) -> str:
        return f"academic:me:{student_id}"

    def _k_semesters(self, student_id: str) -> str:
        return f"academic:semesters:{student_id}"

    def _k_grades(self, student_id: str, semester: str) -> str:
        return f"academic:grades:{student_id}:{semester or 'all'}"

    def _k_schedule(self, student_id: str, xnxq: str) -> str:
        return f"academic:schedule:{student_id}:{xnxq or 'current'}"

    # ========= Core Fix: ensure_user =========
    async def ensure_user(self, *, student_id: str, account: str | None = None) -> AcademicUser:
        """
         确保 academic_user 存在（修复遇到的 FK 报错）
        - semesters/grades/schedule 在 me 之前调用也不会炸
        """
        obj = await self.session.get(AcademicUser, student_id)
        if obj is None:
            obj = AcademicUser(student_id=student_id, account=account or student_id)
            self.session.add(obj)
            await self.session.flush()  #  保证 FK 立刻可用
            return obj

        if account and obj.account != account:
            obj.account = account
        return obj

    async def add_snapshot(self, *, student_id: str, kind: str, scope: str, data: Dict[str, Any], account: str | None = None) -> None:
        await self.ensure_user(student_id=student_id, account=account or student_id)
        self.session.add(
            AcademicSnapshot(
                student_id=student_id,
                kind=kind,
                scope=scope or "",
                data=_truncate_payload(data),
                fetched_at=utc_now(),
            )
        )

    # ========= Cached Read =========
    async def get_cached_me(self, student_id: str) -> Optional[Dict[str, Any]]:
        raw = await self.redis.get(self._k_me(student_id))
        return json.loads(raw) if raw else None

    async def get_cached_semesters(self, student_id: str) -> Optional[Dict[str, Any]]:
        raw = await self.redis.get(self._k_semesters(student_id))
        return json.loads(raw) if raw else None

    async def get_cached_grades(self, student_id: str, semester: str) -> Optional[Dict[str, Any]]:
        raw = await self.redis.get(self._k_grades(student_id, semester))
        return json.loads(raw) if raw else None

    async def get_cached_schedule(self, student_id: str, xnxq: str) -> Optional[Dict[str, Any]]:
        raw = await self.redis.get(self._k_schedule(student_id, xnxq))
        return json.loads(raw) if raw else None

    # ========= Save Me =========
    async def save_me(self, *, student_id: str, account: str, me_data: Dict[str, Any]) -> None:
        u = await self.ensure_user(student_id=student_id, account=account)

        u.name = me_data.get("name") or u.name
        u.college = me_data.get("college") or u.college
        u.major = me_data.get("major") or u.major
        u.class_name = me_data.get("className") or me_data.get("class_name") or u.class_name
        u.enrollment_year = me_data.get("enrollmentYear") or me_data.get("enrollment_year") or u.enrollment_year
        u.study_level = me_data.get("studyLevel") or me_data.get("study_level") or u.study_level
        u.updated_at = utc_now()

        await self.add_snapshot(student_id=student_id, kind="me", scope="", data=me_data, account=account)
        await self.redis.set(self._k_me(student_id), _json_dumps(me_data), ex=24 * 3600)

    # ========= Save Semesters =========
    async def save_semesters(self, *, student_id: str, account: str, payload: Dict[str, Any]) -> None:
        await self.ensure_user(student_id=student_id, account=account)
        await self.add_snapshot(student_id=student_id, kind="semesters", scope="", data=payload, account=account)
        await self.redis.set(self._k_semesters(student_id), _json_dumps(payload), ex=12 * 3600)

    # ========= Save Grades =========
    def _extract_grade_fields(self, row: Dict[str, Any]) -> Dict[str, Optional[str]]:
        def pick(*keys: str) -> Optional[str]:
            for k in keys:
                v = row.get(k)
                if v is not None and str(v).strip():
                    return str(v).strip()
            return None

        return {
            "course_code": pick("课程号", "课程代码", "课程编码", "课程编号"),
            "course_name": pick("课程名称", "课程名", "课程"),
            "credit": pick("学分", "课程学分"),
            "score": pick("成绩", "总评成绩", "最终成绩", "总成绩"),
            "gpa": pick("绩点", "GPA"),
        }

    async def save_grades(self, *, student_id: str, account: str, semester: str, payload: Dict[str, Any]) -> None:
        await self.ensure_user(student_id=student_id, account=account)
        await self.add_snapshot(student_id=student_id, kind="grades", scope=semester or "", data=payload, account=account)

        rows = payload.get("rows") or []
        if isinstance(rows, list):
            for r in rows:
                if not isinstance(r, dict):
                    continue

                raw_hash = AcademicGrade.make_raw_hash(r)
                fields = self._extract_grade_fields(r)

                stmt = (
                    insert(AcademicGrade)
                    .values(
                        student_id=student_id,
                        semester=semester or "",
                        raw_hash=raw_hash,
                        raw_json=r,
                        fetched_at=utc_now(),
                        **fields,
                    )
                    .on_conflict_do_update(
                        constraint="uq_academic_grade_student_semester_hash",
                        set_={
                            "raw_json": r,
                            "fetched_at": utc_now(),
                            "course_code": fields["course_code"],
                            "course_name": fields["course_name"],
                            "credit": fields["credit"],
                            "score": fields["score"],
                            "gpa": fields["gpa"],
                        },
                    )
                )
                await self.session.execute(stmt)

        await self.redis.set(self._k_grades(student_id, semester), _json_dumps(payload), ex=6 * 3600)

    # ========= Save Schedule =========
    async def save_schedule(self, *, student_id: str, account: str, xnxq: str, payload: Dict[str, Any]) -> None:
        await self.ensure_user(student_id=student_id, account=account)
        await self.add_snapshot(student_id=student_id, kind="schedule", scope=xnxq or "", data=payload, account=account)

        # upsert schedule（student_id + semester 唯一）
        q = select(AcademicSchedule).where(
            AcademicSchedule.student_id == student_id,
            AcademicSchedule.semester == (xnxq or ""),
        )
        existing = (await self.session.execute(q)).scalars().first()

        if existing is None:
            existing = AcademicSchedule(
                student_id=student_id,
                semester=xnxq or "",
                current_week=payload.get("currentWeek"),
                raw_json=payload,
                fetched_at=utc_now(),
            )
            self.session.add(existing)
            await self.session.flush()
        else:
            existing.current_week = payload.get("currentWeek")
            existing.raw_json = payload
            existing.fetched_at = utc_now()
            await self.session.flush()

            #  课程表建议“全量覆盖”，避免旧课残留
            await self.session.execute(
                delete(AcademicScheduleCourse).where(AcademicScheduleCourse.schedule_id == existing.id)
            )

        courses = payload.get("courses") or []
        if isinstance(courses, list):
            for c in courses:
                if not isinstance(c, dict):
                    continue

                name = str(c.get("name") or "").strip()
                weekday = int(c.get("weekday") or 0)
                start_section = int(c.get("startSection") or c.get("start_section") or 0)
                end_section = int(c.get("endSection") or c.get("end_section") or 0)
                if not name or weekday <= 0 or start_section <= 0 or end_section <= 0:
                    continue

                raw_hash = AcademicScheduleCourse.make_raw_hash(c)

                stmt = (
                    insert(AcademicScheduleCourse)
                    .values(
                        schedule_id=existing.id,
                        name=name,
                        teacher=(str(c.get("teacher")).strip() if c.get("teacher") else None),
                        location=(str(c.get("location")).strip() if c.get("location") else None),
                        weekday=weekday,
                        start_section=start_section,
                        end_section=end_section,
                        week_range=(str(c.get("weekRange")).strip() if c.get("weekRange") else None),
                        weeks=list(c.get("weeks") or []),
                        raw_hash=raw_hash,
                    )
                    .on_conflict_do_nothing(constraint="uq_academic_schedule_course_schedule_hash")
                )
                await self.session.execute(stmt)

        await self.redis.set(self._k_schedule(student_id, xnxq), _json_dumps(payload), ex=6 * 3600)
