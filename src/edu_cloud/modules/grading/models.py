"""Grading 模块模型 — AI 阅卷 + 人工校对/阅卷（单一权威分数源）。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String, Float, Integer, Text, DateTime, ForeignKey, JSON,
    UniqueConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class Rubric(Base, IdMixin, TimestampMixin):
    __tablename__ = "rubrics"
    __table_args__ = (UniqueConstraint("question_id"),)

    question_id: Mapped[str] = mapped_column(String(36), ForeignKey("questions.id"))
    criteria: Mapped[list] = mapped_column(JSON)
    reference_answer: Mapped[str | None] = mapped_column(Text, default=None)
    source: Mapped[str] = mapped_column(String(20))  # manual | ai_generated
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)


class GradingTask(Base, IdMixin, TimestampMixin):
    __tablename__ = "grading_tasks"

    subject_id: Mapped[str] = mapped_column(String(36), ForeignKey("subjects.id"), index=True)
    question_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("questions.id"), default=None, nullable=True, index=True,
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")
    total: Mapped[int] = mapped_column(default=0)
    completed: Mapped[int] = mapped_column(default=0)
    failed: Mapped[int] = mapped_column(default=0)
    grading_limit: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    error_log: Mapped[dict | None] = mapped_column(JSON, default=None)
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)


class GradingResult(Base, IdMixin, TimestampMixin):
    """单一权威评分记录。

    取代了原 AIGradingResult + TeacherReview + MarkingScore 三表。
    AI 路径、纯人工路径、AI+人工校对 都写同一条记录。

    状态机：
      ai_pending → ai_done → confirmed
      （纯人工直接落 confirmed）

    source 语义（仅 status=confirmed 时有值）：
      ai           — AI 评分被教师 approve（final_score = ai_score）
      ai_override  — AI 评分被教师改分（final_score != ai_score）
      manual       — 纯人工评分（无 AI 打底，ai_score 为 NULL）
    """
    __tablename__ = "grading_results"
    __table_args__ = (
        UniqueConstraint("answer_id"),
        Index("ix_grading_result_school_status", "school_id", "status"),
        Index("ix_grading_result_question", "question_id"),
        Index("ix_grading_result_task", "ai_task_id"),
    )

    answer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("student_answers.id"), nullable=False,
    )
    question_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("questions.id"), nullable=False,
    )
    school_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("schools.id"), nullable=False, index=True,
    )

    ai_task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("grading_tasks.id"), nullable=True, default=None,
    )
    ai_score: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    ai_feedback: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    ai_raw_response: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)

    final_score: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    max_score: Mapped[float] = mapped_column(Float, default=0.0)

    status: Mapped[str] = mapped_column(String(20), default="ai_pending")
    source: Mapped[str | None] = mapped_column(String(20), nullable=True, default=None)

    reviewer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, default=None, index=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None,
    )
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    version: Mapped[int] = mapped_column(Integer, default=1)


class GradingPipelineLog(Base, IdMixin, TimestampMixin):
    """AI 阅卷流水线结构化日志 — 每次评分尝试记录一条。"""
    __tablename__ = "grading_pipeline_logs"
    __table_args__ = (
        Index("ix_pipeline_log_question", "question_id"),
        Index("ix_pipeline_log_school", "school_id"),
        Index("ix_pipeline_log_task", "task_id"),
    )

    answer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("student_answers.id"), nullable=False, index=True,
    )
    question_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("questions.id"), nullable=False,
    )
    task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("grading_tasks.id"), nullable=True, default=None,
    )
    school_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("schools.id"), nullable=False,
    )

    subject_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    question_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pipeline_type: Mapped[str] = mapped_column(String(20))  # two_step / legacy / blank

    image_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_blank: Mapped[bool] = mapped_column(default=False)

    ocr_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ocr_prompt_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ocr_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_blanks_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    char_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    grading_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    grading_prompt_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    grading_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    total_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    error_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class GradingAssignment(Base, IdMixin, TimestampMixin):
    """阅卷任务分配（题块级 + 支持双阅）。

    一个教师可被分配一个科目下的一组题（question_ids），支持 is_second_grading
    标识"二阅"任务（与首阅 paired_assignment_id 关联）。
    """
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
        String(36), ForeignKey("grading_results.id"), nullable=True, index=True
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
