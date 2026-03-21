"""统一用户模型：替代 PlatformUser，支持多角色。"""

import bcrypt
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class User(Base, IdMixin, TimestampMixin):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), default=None, nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), default=None, nullable=True)
    last_login_at = mapped_column(DateTime(timezone=True), default=None, nullable=True)

    def set_password(self, raw: str):
        self.hashed_password = bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode()

    def verify_password(self, raw: str) -> bool:
        if not self.hashed_password:
            return False
        return bcrypt.checkpw(raw.encode(), self.hashed_password.encode())
