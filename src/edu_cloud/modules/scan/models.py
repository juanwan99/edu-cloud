"""Scan 模块模型 — ScanTask + StudentAnswer（从 exam-ai 迁入）。"""
from sqlalchemy import String, Integer, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class ScanTask(Base, IdMixin, TimestampMixin):
    __tablename__ = "scan_tasks"

    subject_id: Mapped[str] = mapped_column(String(36), ForeignKey("subjects.id"))
    side: Mapped[str] = mapped_column(String(1))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # status: pending -> processing -> completed -> failed
    total_images: Mapped[int] = mapped_column(Integer, default=0)
    processed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"))


class StudentAnswer(Base, IdMixin, TimestampMixin):
    __tablename__ = "student_answers"
    __table_args__ = (UniqueConstraint("exam_id", "student_id", "question_id"),)

    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id"))
    subject_id: Mapped[str] = mapped_column(String(36), ForeignKey("subjects.id"))
    student_id: Mapped[str] = mapped_column(String(100))
    question_id: Mapped[str] = mapped_column(String(36), ForeignKey("questions.id"))
    image_path: Mapped[str | None] = mapped_column(String(500), default=None)
    detected_answer: Mapped[str | None] = mapped_column(String(50), default=None)
    score: Mapped[float | None] = mapped_column(default=None)
    is_anomaly: Mapped[bool] = mapped_column(default=False)
    is_absent: Mapped[bool] = mapped_column(default=False)
    fill_ratios: Mapped[dict | None] = mapped_column(JSON, default=None)
    # Phase 1-C: paper-seg 上传时携带题型，供 AI 阅卷选 prompt
    question_type: Mapped[str | None] = mapped_column(String(20), default=None)
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"))
