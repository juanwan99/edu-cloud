"""Student 模块模型 — 合并 exam-ai Student/Class + edu-cloud Student/ClassGroup。"""
from sqlalchemy import String, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class Class(Base, IdMixin, TimestampMixin):
    """班级（合并 exam-ai Class + edu-cloud ClassGroup）。"""
    __tablename__ = "classes"

    name: Mapped[str] = mapped_column(String(100))
    grade: Mapped[str] = mapped_column(String(50))
    grade_number: Mapped[int | None] = mapped_column(Integer, default=None)
    head_teacher_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), default=None
    )
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"))


# Backwards-compatible alias
ClassGroup = Class


class Student(Base, IdMixin, TimestampMixin):
    """学生（合并 exam-ai 字段 + edu-cloud 字段）。"""
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("school_id", "student_number", name="uq_student_school_number"),
    )

    name: Mapped[str] = mapped_column(String(100))
    student_number: Mapped[str] = mapped_column(String(50))
    class_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("classes.id"), default=None)
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"))
    grade: Mapped[str | None] = mapped_column(String(50), default=None)
    gender: Mapped[str | None] = mapped_column(String(10), default=None)
    enrollment_year: Mapped[int | None] = mapped_column(Integer, default=None)
    status: Mapped[str | None] = mapped_column(String(20), default=None)
