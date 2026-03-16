"""云端管理的学校档案。

与 exam-ai 的 School 不同：这里记录的是"哪些学校接入了平台"，
包含 API Key、版本、最后心跳等运维信息。
"""

from datetime import datetime
from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class RegisteredSchool(Base, IdMixin, TimestampMixin):
    __tablename__ = "registered_schools"

    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(50), unique=True)
    address: Mapped[str | None] = mapped_column(String(500), default=None)
    contact: Mapped[str | None] = mapped_column(String(100), default=None)
    contact_phone: Mapped[str | None] = mapped_column(String(50), default=None)

    # 接入管理
    api_key_hash: Mapped[str] = mapped_column(String(200))  # bcrypt hash of API key
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # 运维状态（由心跳更新）
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    client_version: Mapped[str | None] = mapped_column(String(50), default=None)
    exam_ai_port: Mapped[int | None] = mapped_column(default=None)

    # 区域归属（教育局管辖用）
    district: Mapped[str | None] = mapped_column(String(100), default=None)
