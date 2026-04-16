"""Profile 模块模型 — 学生画像（从 exam-ai 迁入）。"""
from datetime import datetime, timezone

from sqlalchemy import String, Float, Integer, ForeignKey, JSON, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class StudentExamSnapshot(Base, IdMixin, TimestampMixin):
    """单次考试快照 — 成绩+排名+知识点维度，不可变。"""
    __tablename__ = "student_exam_snapshots"
    __table_args__ = (UniqueConstraint("student_id", "exam_id", "subject_code"),)

    student_id: Mapped[str] = mapped_column(String(100))
    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id"))
    subject_code: Mapped[str] = mapped_column(String(50))

    total_score: Mapped[float] = mapped_column(Float)
    max_score: Mapped[float] = mapped_column(Float)
    score_rate: Mapped[float] = mapped_column(Float)

    class_rank: Mapped[int | None] = mapped_column(Integer, default=None)
    grade_rank: Mapped[int | None] = mapped_column(Integer, default=None)
    class_size: Mapped[int | None] = mapped_column(Integer, default=None)
    grade_size: Mapped[int | None] = mapped_column(Integer, default=None)

    class_id_at_exam: Mapped[str | None] = mapped_column(String(36), default=None)

    knowledge_scores: Mapped[dict | None] = mapped_column(JSON, default=None)
    error_summary: Mapped[dict | None] = mapped_column(JSON, default=None)

    exam_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"))


class StudentKnowledgeMastery(Base, IdMixin, TimestampMixin):
    """知识点掌握度 — 每次考试后增量更新。"""
    __tablename__ = "student_knowledge_mastery"
    __table_args__ = (UniqueConstraint("student_id", "knowledge_point_id"),)

    student_id: Mapped[str] = mapped_column(String(100))
    knowledge_point_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_points.id"))

    mastery_level: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    partial_count: Mapped[int] = mapped_column(Integer, default=0)

    trend: Mapped[str] = mapped_column(String(20), default="stable")
    recent_scores: Mapped[list | None] = mapped_column(JSON, default=None)

    last_exam_id: Mapped[str | None] = mapped_column(String(36), default=None)
    last_exam_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"))


class StudentErrorPattern(Base, IdMixin, TimestampMixin):
    """错误模式 — 从错题本聚合。"""
    __tablename__ = "student_error_patterns"
    __table_args__ = (UniqueConstraint("student_id", "subject_code"),)

    student_id: Mapped[str] = mapped_column(String(100))
    subject_code: Mapped[str] = mapped_column(String(50))

    error_distribution: Mapped[dict] = mapped_column(JSON, default=dict)

    careless_rate: Mapped[float | None] = mapped_column(Float, default=None)
    unanswered_rate: Mapped[float | None] = mapped_column(Float, default=None)

    total_errors: Mapped[int] = mapped_column(Integer, default=0)
    exam_count: Mapped[int] = mapped_column(Integer, default=0)
    snapshot_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"))
