"""Exam 模块模型 — 合并 exam-ai 考试模型 + edu-cloud 联考模型。

包含：
- Exam, Subject, Question（从 exam-ai 迁入，加 school_id FK）
- ExamResult（保留为聚合视图，由 pipeline 填充）
- JointExam, JointExamParticipant, JointExamStudentResult（原 edu-cloud）
"""
from datetime import datetime, timezone

from sqlalchemy import (
    String, Integer, Float, Text, ForeignKey, JSON, Boolean, DateTime,
    UniqueConstraint, Index, Column,
)
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


# ── 题型词汇表（unified 2026-04-16 Phase 1-A）───────────────────
QUESTION_TYPE_CHOICE = "choice"
QUESTION_TYPE_MULTI_CHOICE = "multi_choice"
QUESTION_TYPE_FILL_BLANK = "fill_blank"
QUESTION_TYPE_ESSAY = "essay"
QUESTION_TYPE_DRAWING = "drawing"

QUESTION_TYPES_OBJECTIVE = (QUESTION_TYPE_CHOICE, QUESTION_TYPE_MULTI_CHOICE)
QUESTION_TYPES_SUBJECTIVE = (QUESTION_TYPE_FILL_BLANK, QUESTION_TYPE_ESSAY, QUESTION_TYPE_DRAWING)
QUESTION_TYPES_ALL = QUESTION_TYPES_OBJECTIVE + QUESTION_TYPES_SUBJECTIVE
QUESTION_TYPES_VISUAL = (QUESTION_TYPE_DRAWING,)


# ── exam-ai 迁入模型 ──────────────────────────────────────────────

class Exam(Base, IdMixin, TimestampMixin):
    __tablename__ = "exams"

    name: Mapped[str] = mapped_column(String(200))
    card_title: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    # status: draft -> scanning -> grading -> reviewing -> completed
    exam_type: Mapped[str | None] = mapped_column(String(20), default=None)
    grade_scope: Mapped[str | None] = mapped_column(String(50), default=None)
    semester: Mapped[str | None] = mapped_column(String(50), default=None)
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    # edu-cloud 原有字段（sync 用）
    subject_code: Mapped[str | None] = mapped_column(String(50), default=None)
    subject_name: Mapped[str | None] = mapped_column(String(100), default=None)
    max_score: Mapped[float | None] = mapped_column(Float, default=None)
    exam_date: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    source: Mapped[str | None] = mapped_column(String(50), default=None)


class Subject(Base, IdMixin, TimestampMixin):
    __tablename__ = "subjects"
    __table_args__ = (UniqueConstraint("exam_id", "code"),)

    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    code: Mapped[str] = mapped_column(String(50))
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    exam_start: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    exam_end: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    exam_room: Mapped[str | None] = mapped_column(String(100), default=None)
    proctor_ids: Mapped[list | None] = mapped_column(JSON, default=None)


class Question(Base, IdMixin, TimestampMixin):
    __tablename__ = "questions"
    __table_args__ = (
        UniqueConstraint("subject_id", "name", name="uq_question_subject_name"),
    )

    subject_id: Mapped[str] = mapped_column(String(36), ForeignKey("subjects.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    question_type: Mapped[str] = mapped_column(String(20))  # choice / multi_choice / fill_blank / essay
    max_score: Mapped[float] = mapped_column(default=0.0)
    region_id: Mapped[str | None] = mapped_column(String(50), default=None)
    knowledge_points: Mapped[dict | None] = mapped_column(JSON, default=None)
    correct_answer: Mapped[str | None] = mapped_column(String(50), default=None)
    content: Mapped[str | None] = mapped_column(Text, default=None)
    content_images: Mapped[list | None] = mapped_column(JSON, default=None)
    reference_answer: Mapped[str | None] = mapped_column(Text, default=None)
    reference_answer_images: Mapped[list | None] = mapped_column(JSON, default=None)
    parent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("questions.id"), default=None, index=True)
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)


# ── ExamResult（聚合视图，由 pipeline 模块填充）─────────────────

class ExamResult(Base, IdMixin, TimestampMixin):
    __tablename__ = "exam_results"

    exam_id = Column(String, ForeignKey("exams.id"), nullable=False, index=True)
    student_id = Column(String, ForeignKey("students.id"), nullable=False, index=True)
    school_id = Column(String, ForeignKey("schools.id"), nullable=False, index=True)
    total_score = Column(Float, nullable=False)
    detail_scores = Column(JSON, nullable=True)
    rank_in_class = Column(Integer, nullable=True)
    rank_in_grade = Column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("exam_id", "student_id", name="uq_result_exam_student"),
    )


# ── 联考模型（原 edu-cloud）──────────────────────────────────────

class JointExam(Base, IdMixin, TimestampMixin):
    """联考主表。"""
    __tablename__ = "joint_exams"

    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    subjects: Mapped[list] = mapped_column(JSON, default=list)
    creator_school_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("schools.id"), default=None, index=True
    )
    template_file_path: Mapped[str | None] = mapped_column(String(500), default=None)
    answer_detail_schema: Mapped[dict | None] = mapped_column(JSON, default=None)


class JointExamParticipant(Base, IdMixin, TimestampMixin):
    """联考参与学校。"""
    __tablename__ = "joint_exam_participants"

    joint_exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("joint_exams.id"), index=True)
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    is_creator: Mapped[bool] = mapped_column(Boolean, default=False)
    student_count: Mapped[int | None] = mapped_column(Integer, default=None)
    score_upload_count: Mapped[int | None] = mapped_column(Integer, default=None)


class JointExamStudentResult(Base, IdMixin, TimestampMixin):
    """联考学生成绩明细。"""
    __tablename__ = "joint_exam_student_results"

    joint_exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("joint_exams.id"), index=True)
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    subject_code: Mapped[str] = mapped_column(String(50))
    student_name: Mapped[str] = mapped_column(String(100))
    student_number: Mapped[str] = mapped_column(String(100))
    total_score: Mapped[float] = mapped_column(Float)
    detail_scores: Mapped[list] = mapped_column(JSON, default=list)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint(
            "joint_exam_id", "school_id", "subject_code", "student_number",
            name="uq_result_student",
        ),
        Index("ix_result_ranking", "joint_exam_id", "subject_code", "total_score"),
        Index("ix_result_school", "joint_exam_id", "school_id"),
    )
