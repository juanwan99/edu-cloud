"""Conduct 模块模型 — 学生操行/德育积分系统的 8 张表。"""

from datetime import datetime, timezone, date

from sqlalchemy import (
    String, Integer, Boolean, Date, DateTime, Text, JSON,
    ForeignKey, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class StudentProfile(Base, IdMixin, TimestampMixin):
    """学生 PII 扩展（1-to-1 with students）。"""
    __tablename__ = "student_profiles"

    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("students.id"), unique=True, nullable=False,
    )
    avatar: Mapped[str | None] = mapped_column(String(10), default=None, nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, default=None, nullable=True)
    ethnicity: Mapped[str | None] = mapped_column(String(20), default=None, nullable=True)
    id_card_number: Mapped[str | None] = mapped_column(Text, default=None, nullable=True)
    blood_type: Mapped[str | None] = mapped_column(String(5), default=None, nullable=True)
    health_notes: Mapped[str | None] = mapped_column(Text, default=None, nullable=True)
    home_address: Mapped[str | None] = mapped_column(Text, default=None, nullable=True)
    emergency_contact_name: Mapped[str | None] = mapped_column(
        String(50), default=None, nullable=True,
    )
    emergency_contact_phone: Mapped[str | None] = mapped_column(
        String(20), default=None, nullable=True,
    )
    verify_code: Mapped[str | None] = mapped_column(Text, default=None, nullable=True)


class ConductClassConfig(Base, IdMixin, TimestampMixin):
    """班级操行配置。"""
    __tablename__ = "conduct_class_configs"

    class_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("classes.id"), unique=True, nullable=False,
    )
    invite_code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    verify_code_type: Mapped[str] = mapped_column(
        String(10), default="id_card", nullable=False,
    )
    required_parent_fields: Mapped[dict | None] = mapped_column(
        JSON, default=None, nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    alert_threshold: Mapped[int | None] = mapped_column(Integer, default=None, nullable=True)


class ConductRuleCategory(Base, IdMixin):
    """班规分类。"""
    __tablename__ = "conduct_rule_categories"

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    class_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("classes.id"), index=True, default=None, nullable=True,
    )
    school_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("schools.id"), index=True, default=None, nullable=True,
    )
    scope: Mapped[str] = mapped_column(String(10), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ConductRuleItem(Base, IdMixin):
    """班规条目。"""
    __tablename__ = "conduct_rule_items"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    category_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conduct_rule_categories.id"), index=True, nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ConductRecord(Base, IdMixin):
    """操行积分记录。"""
    __tablename__ = "conduct_records"

    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("students.id"), index=True, nullable=False,
    )
    class_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("classes.id"), index=True, nullable=False,
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    operator_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=False,
    )
    source: Mapped[str] = mapped_column(String(10), default="manual", nullable=False)
    rule_item_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("conduct_rule_items.id"), index=True, default=None, nullable=True,
    )
    semester_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("conduct_semesters.id"), index=True, default=None, nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ConductNotification(Base, IdMixin):
    """家长端通知（积分变动触发）"""
    __tablename__ = "conduct_notifications"

    parent_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=False,
    )
    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("students.id"), index=True, nullable=False,
    )
    record_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("conduct_records.id"), nullable=True,
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class ConductGroup(Base, IdMixin):
    """小组。"""
    __tablename__ = "conduct_groups"
    __table_args__ = (
        UniqueConstraint("class_id", "name", name="uq_conduct_group_class_name"),
    )

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    class_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("classes.id"), index=True, nullable=False,
    )
    avatar: Mapped[str | None] = mapped_column(String(10), default=None, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ConductGroupMember(Base, IdMixin):
    """小组成员。"""
    __tablename__ = "conduct_group_members"
    __table_args__ = (
        UniqueConstraint("student_id", "group_id", name="uq_conduct_group_member"),
    )

    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("students.id"), index=True, nullable=False,
    )
    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conduct_groups.id"), index=True, nullable=False,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class ConductSemester(Base, IdMixin):
    """学期。"""
    __tablename__ = "conduct_semesters"

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    school_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("schools.id"), index=True, default=None, nullable=True,
    )
    class_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("classes.id"), index=True, default=None, nullable=True,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
