"""Marking 模块模型 — 手动批改（从 exam-ai 迁入）。"""
from sqlalchemy import String, Float, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class MarkingAssignment(Base, IdMixin, TimestampMixin):
    __tablename__ = "marking_assignments"
    __table_args__ = (UniqueConstraint("question_id", "teacher_id"),)

    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id"))
    question_id: Mapped[str] = mapped_column(String(36), ForeignKey("questions.id"))
    teacher_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"))


class MarkingScore(Base, IdMixin, TimestampMixin):
    __tablename__ = "marking_scores"
    __table_args__ = (UniqueConstraint("answer_id", "marker_id"),)

    answer_id: Mapped[str] = mapped_column(String(36), ForeignKey("student_answers.id"))
    question_id: Mapped[str] = mapped_column(String(36), ForeignKey("questions.id"))
    marker_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    score: Mapped[float] = mapped_column(Float)
    max_score: Mapped[float] = mapped_column(Float)
    comment: Mapped[str | None] = mapped_column(Text, default=None)
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"))
