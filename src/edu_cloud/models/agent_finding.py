"""Agent 发现与任务模型 — AgentFinding + AgentTask。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TenantMixin, TimestampMixin


class AgentFinding(Base, IdMixin, TenantMixin, TimestampMixin):
    """Agent 巡检发现的异常/洞察（幂等，通过 idempotency_key 去重）。"""
    __tablename__ = "agent_findings"

    finding_type: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(20))
    target_type: Mapped[str] = mapped_column(String(30))
    target_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    summary: Mapped[str] = mapped_column(Text)
    detail: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20))
    notify_roles: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(500), index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_finding_idempotency"),
    )


class AgentTask(Base, IdMixin, TenantMixin, TimestampMixin):
    """Agent 生成的待办任务（可选关联 finding）。"""
    __tablename__ = "agent_tasks"

    finding_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("agent_findings.id"), nullable=True,
    )
    task_type: Mapped[str] = mapped_column(String(50))
    assignee_role: Mapped[str] = mapped_column(String(50))
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20))
