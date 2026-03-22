"""学校档案模型。"""

from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class School(Base, IdMixin, TimestampMixin):
    __tablename__ = "schools"

    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(50), unique=True)
    address: Mapped[str | None] = mapped_column(String(500), default=None)
    contact: Mapped[str | None] = mapped_column(String(100), default=None)
    contact_phone: Mapped[str | None] = mapped_column(String(50), default=None)

    # 接入管理（sync 认证用，合并完成后移除）
    api_key_hash: Mapped[str | None] = mapped_column(String(200), default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # 区域归属（教育局管辖用）
    district: Mapped[str | None] = mapped_column(String(100), default=None)
