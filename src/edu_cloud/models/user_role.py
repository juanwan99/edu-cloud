"""用户角色关联表：支持一人多角色 + scope 约束。"""

from sqlalchemy import String, ForeignKey, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column
from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class UserRole(Base, IdMixin, TimestampMixin):
    __tablename__ = "user_roles"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)

    # Scope: 角色作用域
    school_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("schools.id"), default=None, nullable=True, index=True
    )
    grade_ids: Mapped[list | None] = mapped_column(JSON, default=None, nullable=True)
    class_ids: Mapped[list | None] = mapped_column(JSON, default=None, nullable=True)
    subject_codes: Mapped[list | None] = mapped_column(JSON, default=None, nullable=True)

    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
