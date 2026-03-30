"""Grading 模块模型 — AI 阅卷（从 exam-ai 迁入）。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, Text, ForeignKey, JSON, UniqueConstraint, Index
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


class GradingAssignment(Base, IdMixin, TimestampMixin):
    """题块级阅卷任务分配。"""
    __tablename__ = "grading_assignments"

    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id"), index=True)
    subject_id: Mapped[str] = mapped_column(String(36), ForeignKey("subjects.id"), index=True)
    question_ids: Mapped[list] = mapped_column(JSON)
    assigned_to: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    graded_count: Mapped[int] = mapped_column(default=0)
    total_count: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    is_second_grading: Mapped[bool] = mapped_column(default=False)
    paired_assignment_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("grading_assignments.id"), nullable=True
    )

    __table_args__ = (
        Index("ix_assignment_exam_teacher", "exam_id", "assigned_to"),
    )


class GradingQualityCheck(Base, IdMixin, TimestampMixin):
    """质量抽检记录。"""
    __tablename__ = "grading_quality_checks"

    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id"), index=True)
    subject_id: Mapped[str] = mapped_column(String(36), ForeignKey("subjects.id"), index=True)
    question_id: Mapped[str] = mapped_column(String(36), ForeignKey("questions.id"))
    check_type: Mapped[str] = mapped_column(String(20))
    original_result_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("ai_grading_results.id"), nullable=True
    )
    original_grader_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    checker_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    original_score: Mapped[float] = mapped_column()
    check_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    deviation: Mapped[Optional[float]] = mapped_column(nullable=True)
    severity: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
