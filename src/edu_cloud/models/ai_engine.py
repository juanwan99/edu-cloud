"""ORM models for the Pydantic AI engine layer (Step 2).

Tables: ai_artifacts, ai_agent_trace, ai_agent_trace_event
"""
from __future__ import annotations

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TenantMixin, TimestampMixin


class AiArtifact(Base, IdMixin, TenantMixin, TimestampMixin):
    __tablename__ = "ai_artifacts"

    artifact_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    source_tool: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(20))
    pii_level: Mapped[str] = mapped_column(String(20), default="none")
    summary_json: Mapped[str] = mapped_column(Text, default="{}")
    preview_json: Mapped[str] = mapped_column(Text, default="{}")
    storage_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)


class AiAgentTrace(Base, IdMixin, TenantMixin, TimestampMixin):
    __tablename__ = "ai_agent_trace"

    run_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str] = mapped_column(String(36))
    role: Mapped[str] = mapped_column(String(50))
    tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    model_slot: Mapped[str] = mapped_column(String(50), default="ai-chat")
    budget_initial_json: Mapped[str] = mapped_column(Text, default="{}")
    budget_final_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(20), default="running")
    event_count: Mapped[int] = mapped_column(Integer, default=0)


class AiAgentTraceEvent(Base, IdMixin, TimestampMixin):
    __tablename__ = "ai_agent_trace_event"

    trace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_agent_trace.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(30))
    tool_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    args_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pii_level: Mapped[str] = mapped_column(String(20), default="none")

    __table_args__ = (
        Index("ix_trace_event_trace_seq", "trace_id", "seq"),
    )
