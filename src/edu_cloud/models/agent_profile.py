from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class AgentProfile(Base, IdMixin, TimestampMixin):
    __tablename__ = "agent_profiles"

    owner_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    profile_type: Mapped[str] = mapped_column(String(20), default="employee")
    display_name: Mapped[str] = mapped_column(String(100))
    preferences: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    memory_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("owner_user_id", "school_id", name="uq_profile_user_school"),
    )


class AgentRun(Base, IdMixin):
    __tablename__ = "agent_runs"

    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_profiles.id"), index=True
    )
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    tools_resolved: Mapped[list] = mapped_column(JSON, default=list)
    tools_selected: Mapped[list] = mapped_column(JSON, default=list)
    model_used: Mapped[str] = mapped_column(String(50))
    model_tier: Mapped[str] = mapped_column(String(20))
    intent_domains: Mapped[list] = mapped_column(JSON, default=list)
    token_input: Mapped[int] = mapped_column(default=0)
    token_output: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
