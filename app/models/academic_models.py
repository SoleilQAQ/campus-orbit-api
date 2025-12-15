from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

#  必须是项目唯一的 Base（确保 Alembic target_metadata 能看到）
from app.db.base import Base  # 按项目实际路径调整


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AcademicUser(Base):
    __tablename__ = "academic_user"

    student_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account: Mapped[str] = mapped_column(String(64), nullable=False)

    name: Mapped[Optional[str]] = mapped_column(String(128))
    college: Mapped[Optional[str]] = mapped_column(String(256))
    major: Mapped[Optional[str]] = mapped_column(String(256))
    class_name: Mapped[Optional[str]] = mapped_column(String(128))
    enrollment_year: Mapped[Optional[str]] = mapped_column(String(16))
    study_level: Mapped[Optional[str]] = mapped_column(String(64))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    snapshots: Mapped[list["AcademicSnapshot"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    grades: Mapped[list["AcademicGrade"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    schedules: Mapped[list["AcademicSchedule"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class AcademicSnapshot(Base):
    __tablename__ = "academic_snapshot"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("academic_user.student_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    kind: Mapped[str] = mapped_column(String(32), nullable=False)   # me/semesters/grades/schedule
    scope: Mapped[str] = mapped_column(String(64), default="")      # grades: semester；schedule: xnxq

    data: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    user: Mapped["AcademicUser"] = relationship(back_populates="snapshots")

    __table_args__ = (
        Index("ix_academic_snapshot_student_kind_scope_time", "student_id", "kind", "scope", "fetched_at"),
    )


class AcademicGrade(Base):
    __tablename__ = "academic_grade"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("academic_user.student_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    semester: Mapped[str] = mapped_column(String(64), default="", index=True)

    course_code: Mapped[Optional[str]] = mapped_column(String(64))
    course_name: Mapped[Optional[str]] = mapped_column(String(256))
    credit: Mapped[Optional[str]] = mapped_column(String(32))
    score: Mapped[Optional[str]] = mapped_column(String(32))
    gpa: Mapped[Optional[str]] = mapped_column(String(32))

    raw_hash: Mapped[str] = mapped_column(String(40), nullable=False)
    raw_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    user: Mapped["AcademicUser"] = relationship(back_populates="grades")

    __table_args__ = (
        UniqueConstraint("student_id", "semester", "raw_hash", name="uq_academic_grade_student_semester_hash"),
        Index("ix_academic_grade_student_semester_time", "student_id", "semester", "fetched_at"),
    )

    @staticmethod
    def make_raw_hash(row: Dict[str, Any]) -> str:
        s = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha1(s.encode("utf-8")).hexdigest()


class AcademicSchedule(Base):
    __tablename__ = "academic_schedule"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("academic_user.student_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    semester: Mapped[str] = mapped_column(String(64), default="", index=True)  # xnxq01id
    current_week: Mapped[Optional[int]] = mapped_column(Integer)

    raw_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    user: Mapped["AcademicUser"] = relationship(back_populates="schedules")
    courses: Mapped[list["AcademicScheduleCourse"]] = relationship(back_populates="schedule", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("student_id", "semester", name="uq_academic_schedule_student_semester"),
    )


class AcademicScheduleCourse(Base):
    __tablename__ = "academic_schedule_course"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_schedule.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    teacher: Mapped[Optional[str]] = mapped_column(String(128))
    location: Mapped[Optional[str]] = mapped_column(String(256))

    weekday: Mapped[int] = mapped_column(Integer, nullable=False)        # 1-7
    start_section: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-12
    end_section: Mapped[int] = mapped_column(Integer, nullable=False)

    week_range: Mapped[Optional[str]] = mapped_column(String(128))
    weeks: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False, default=list)

    raw_hash: Mapped[str] = mapped_column(String(40), nullable=False)

    schedule: Mapped["AcademicSchedule"] = relationship(back_populates="courses")

    __table_args__ = (
        UniqueConstraint("schedule_id", "raw_hash", name="uq_academic_schedule_course_schedule_hash"),
        Index("ix_academic_schedule_course_schedule_weekday", "schedule_id", "weekday"),
    )

    @staticmethod
    def make_raw_hash(payload: Dict[str, Any]) -> str:
        s = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha1(s.encode("utf-8")).hexdigest()
