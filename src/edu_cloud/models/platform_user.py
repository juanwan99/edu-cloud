"""平台级用户：区管理员、联考协调员等。

与 exam-ai 的 User 不同：这里是云端平台的操作者，
不属于任何学校，管理多所学校的事务。
"""

import bcrypt
from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column
from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class PlatformUser(Base, IdMixin, TimestampMixin):
    __tablename__ = "platform_users"

    username: Mapped[str] = mapped_column(String(100), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    hashed_password: Mapped[str] = mapped_column(String(200), default="")
    role: Mapped[str] = mapped_column(String(30))
    # roles: platform_admin / district_admin / exam_coordinator / observer

    # district_admin: 管辖哪些区域
    districts: Mapped[list | None] = mapped_column(JSON, default=None)
    # exam_coordinator: 可操作哪些学校
    school_ids: Mapped[list | None] = mapped_column(JSON, default=None)

    def set_password(self, raw: str):
        self.hashed_password = bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode()

    def verify_password(self, raw: str) -> bool:
        return bcrypt.checkpw(raw.encode(), self.hashed_password.encode())
