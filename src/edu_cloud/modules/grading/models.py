"""Grading 模块模型 — AI 阅卷（从 exam-ai 迁入）。"""
from sqlalchemy import String, Float, Text, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class Rubric(Base, IdMixin, TimestampMixin):
    __tablename__ = "rubrics"
    __table_args__ = (UniqueConstraint("question_id"),)

    question_id: Mapped[str] = mapped_column(String(36), ForeignKey("questions.id"))
    criteria: Mapped[dict] = mapped_column(JSON)
    reference_answer: Mapped[str | None] = mapped_column(Text, default=None)
    source: Mapped[str] = mapped_column(String(20))  # manual | ai_generated
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"))


class GradingTask(Base, IdMixin, TimestampMixin):
    __tablename__ = "grading_tasks"

    subject_id: Mapped[str] = mapped_column(String(36), ForeignKey("subjects.id"))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    total: Mapped[int] = mapped_column(default=0)
    completed: Mapped[int] = mapped_column(default=0)
    failed: Mapped[int] = mapped_column(default=0)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    error_log: Mapped[dict | None] = mapped_column(JSON, default=None)
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"))


class AIGradingResult(Base, IdMixin, TimestampMixin):
    __tablename__ = "ai_grading_results"
    __table_args__ = (UniqueConstraint("answer_id"),)

    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("grading_tasks.id"))
    answer_id: Mapped[str] = mapped_column(String(36), ForeignKey("student_answers.id"))
    question_id: Mapped[str] = mapped_column(String(36), ForeignKey("questions.id"))
    score: Mapped[float] = mapped_column(Float, default=0.0)
    max_score: Mapped[float] = mapped_column(Float, default=0.0)
    feedback: Mapped[str | None] = mapped_column(Text, default=None)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    raw_response: Mapped[dict | None] = mapped_column(JSON, default=None)
    review_status: Mapped[str] = mapped_column(String(20), default="pending")
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"))


class TeacherReview(Base, IdMixin, TimestampMixin):
    __tablename__ = "teacher_reviews"
    __table_args__ = (UniqueConstraint("result_id"),)

    result_id: Mapped[str] = mapped_column(String(36), ForeignKey("ai_grading_results.id"))
    reviewer_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(20))  # approve | override
    adjusted_score: Mapped[float | None] = mapped_column(Float, default=None)
    comment: Mapped[str | None] = mapped_column(Text, default=None)
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"))
