"""Bank 模块模型 — 题库 + 学生错题本（从 exam-ai 迁入）。"""
from datetime import datetime

from sqlalchemy import String, Float, Integer, Text, Boolean, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class BankQuestion(Base, IdMixin, TimestampMixin):
    """学校题库 — 从考试自动入库，积累统计属性。"""
    __tablename__ = "bank_questions"
    __table_args__ = (UniqueConstraint("school_id", "source_question_id"),)

    content_text: Mapped[str | None] = mapped_column(Text, default=None)
    content_image: Mapped[str | None] = mapped_column(String(500), default=None)
    question_type: Mapped[str] = mapped_column(String(20))
    max_score: Mapped[float] = mapped_column(Float)
    correct_answer: Mapped[str | None] = mapped_column(String(200), default=None)
    solution: Mapped[str | None] = mapped_column(Text, default=None)

    source_exam_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("exams.id"), default=None, index=True)
    source_question_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("questions.id"), default=None, index=True)

    difficulty: Mapped[float | None] = mapped_column(Float, default=None)
    discrimination: Mapped[float | None] = mapped_column(Float, default=None)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    common_errors: Mapped[dict | None] = mapped_column(JSON, default=None)

    embedding: Mapped[str | None] = mapped_column(String(2000), default=None)
    tags: Mapped[list | None] = mapped_column(JSON, default=None)
    bloom_level: Mapped[str | None] = mapped_column(String(20), default=None)

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)


class StudentErrorBook(Base, IdMixin, TimestampMixin):
    """学生个人错题本 — AI 阅卷后自动收集。"""
    __tablename__ = "student_error_books"
    __table_args__ = (UniqueConstraint("student_id", "question_id"),)

    student_id: Mapped[str] = mapped_column(String(100))
    question_id: Mapped[str] = mapped_column(String(36), ForeignKey("questions.id"), index=True)
    bank_question_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("bank_questions.id"), default=None, index=True)
    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id"), index=True)

    student_answer_image: Mapped[str | None] = mapped_column(String(500), default=None)
    student_score: Mapped[float] = mapped_column(Float)
    max_score: Mapped[float] = mapped_column(Float)
    correct_answer: Mapped[str | None] = mapped_column(String(200), default=None)

    ai_feedback: Mapped[str | None] = mapped_column(Text, default=None)
    error_type: Mapped[str | None] = mapped_column(String(50), default=None)
    sub_question: Mapped[str | None] = mapped_column(String(50), default=None)
    knowledge_point_ids: Mapped[list | None] = mapped_column(JSON, default=None)

    mastery_status: Mapped[str] = mapped_column(String(20), default="unmastered")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    last_retry_score: Mapped[float | None] = mapped_column(Float, default=None)
    last_retry_at: Mapped[datetime | None] = mapped_column(default=None)

    source: Mapped[str] = mapped_column(String(20), default="auto")
    is_starred: Mapped[bool] = mapped_column(Boolean, default=False)

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
