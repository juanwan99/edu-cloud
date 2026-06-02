# DEPRECATED: 未使用的模型，保留仅因 alembic 迁移创建了对应表。
# 正式删除需先写 DROP TABLE 迁移。
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class AgentMemory(Base, IdMixin, TimestampMixin):
    __tablename__ = "agent_memories"

    school_id: Mapped[str] = mapped_column(String(36), index=True)
    session_id: Mapped[str] = mapped_column(String(36))
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    memory_type: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
