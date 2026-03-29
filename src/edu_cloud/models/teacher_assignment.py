from sqlalchemy import String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class TeacherAssignment(Base, IdMixin, TimestampMixin):
    """教师排课记录：哪个教师在哪个学期教哪个班的什么科目。"""
    __tablename__ = "teacher_assignments"
    __table_args__ = (
        UniqueConstraint("user_id", "class_id", "subject_code", "semester",
                         name="uq_teacher_assignment"),
    )

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    class_id: Mapped[str] = mapped_column(String(36), ForeignKey("classes.id"), index=True)
    subject_code: Mapped[str] = mapped_column(String(50))
    semester: Mapped[str] = mapped_column(String(20))
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
