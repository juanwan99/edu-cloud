"""Persistent agent memory across sessions (Design §6)."""
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
    memory_type: Mapped[str] = mapped_column(String(20))  # finding | preference | follow_up
    content: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # student | class | school
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
