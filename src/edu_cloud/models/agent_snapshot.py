"""考试分析快照与班级报告模型。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TenantMixin, TimestampMixin


class ExamAnalysisSnapshot(Base, IdMixin, TenantMixin, TimestampMixin):
    """考试分析快照（不可变，版本递增）。"""
    __tablename__ = "exam_analysis_snapshot"

    exam_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("exams.id"), index=True,
    )
    snapshot_type: Mapped[str] = mapped_column(String(30))
    target_type: Mapped[str] = mapped_column(String(20))
    target_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    subject_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    semester: Mapped[str] = mapped_column(String(30))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20))
    metrics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
    )


class ClassExamReport(Base, IdMixin, TenantMixin, TimestampMixin):
    """班级考试报告（按班聚合的分析结果）。"""
    __tablename__ = "class_exam_report"

    exam_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("exams.id"), index=True,
    )
    class_id: Mapped[str] = mapped_column(String(36), index=True)
    grade_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    class_avg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    grade_avg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vs_last_exam: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    metrics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20))
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
    )
