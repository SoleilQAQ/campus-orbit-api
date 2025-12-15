import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db_compat import Base


def utcnow():
    return datetime.now(timezone.utc)


class PlatformUser(Base):
    __tablename__ = "platform_user"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 登录名：管理员用用户名；学生建议直接用学号
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    # admin / student
    role: Mapped[str] = mapped_column(String(16), index=True, nullable=False)

    # 学生可存 student_id（学号），管理员可为空
    student_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)

    # 管理员需要密码；学生不存密码（学生密码用教务系统校验）
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class WeatherSwitch(Base):
    __tablename__ = "weather_switch"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # “备份接口”思路：永远能返回 last_backup_json（由定时/管理员手动触发更新也行）
    last_backup_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class AiPromptTemplate(Base):
    __tablename__ = "ai_prompt_template"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # prompt 模板正文
    role: Mapped[str] = mapped_column(String(16), default="student", nullable=False)  # 默认 student 可见
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AiAnalysisHistory(Base):
    __tablename__ = "ai_analysis_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    semester: Mapped[str] = mapped_column(String(32), default="", nullable=False)

    prompt_name: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    input_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    output_text: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
