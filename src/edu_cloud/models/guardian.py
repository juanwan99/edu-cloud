"""家长-学生绑定关系表。"""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TenantMixin, TimestampMixin


class GuardianStudentLink(Base, IdMixin, TenantMixin, TimestampMixin):
    """家长与学生的绑定关系（一个家长可绑定多个学生）。"""
    __tablename__ = "guardian_student_links"

    guardian_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), index=True,
    )
    student_id: Mapped[str] = mapped_column(String(100), index=True)
    relationship: Mapped[str] = mapped_column(String(20))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("guardian_user_id", "student_id", name="uq_guardian_student"),
    )
