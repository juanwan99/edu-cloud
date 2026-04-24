"""作业模块模型 — HomeworkTask + HomeworkSubmission。"""
from sqlalchemy import String, Float, Text, ForeignKey, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class HomeworkTask(Base, IdMixin, TimestampMixin):
    """作业任务。"""
    __tablename__ = "homework_tasks"
    __table_args__ = (
        Index("ix_hw_task_school_status", "school_id", "status"),
        Index("ix_hw_task_school_class", "school_id", "class_id"),
        Index("ix_hw_task_assigned_by", "assigned_by"),
    )

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    task_type: Mapped[str] = mapped_column(String(20), nullable=False, default="regular")
    subject_code: Mapped[str] = mapped_column(String(20), nullable=False)
    class_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("classes.id"), default=None, index=True)
    assigned_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    exam_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("exams.id"), default=None, index=True)
    deadline: Mapped[str | None] = mapped_column(DateTime, default=None)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    content: Mapped[str | None] = mapped_column(Text, default=None)
    grading_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")


class HomeworkSubmission(Base, IdMixin, TimestampMixin):
    """作业提交记录。"""
    __tablename__ = "homework_submissions"
    __table_args__ = (
        UniqueConstraint("task_id", "student_id", name="uq_hw_submission_task_student"),
        Index("ix_hw_sub_task_status", "task_id", "status"),
    )

    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("homework_tasks.id"), nullable=False)
    student_id: Mapped[str] = mapped_column(String(36), ForeignKey("students.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    score: Mapped[float | None] = mapped_column(Float, default=None)
    feedback: Mapped[str | None] = mapped_column(Text, default=None)
    submit_time: Mapped[str | None] = mapped_column(DateTime, default=None)
    content: Mapped[str | None] = mapped_column(Text, default=None)
    graded_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), default=None, index=True)
    graded_at: Mapped[str | None] = mapped_column(DateTime, default=None)
