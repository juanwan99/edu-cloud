"""工作流引擎数据模型 — WorkflowRun + WorkflowStep。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TenantMixin, TimestampMixin


class WorkflowRun(Base, IdMixin, TenantMixin, TimestampMixin):
    """工作流执行实例（幂等，通过 idempotency_key 去重）。"""
    __tablename__ = "workflow_runs"

    workflow_name: Mapped[str] = mapped_column(String(100))
    trigger_type: Mapped[str] = mapped_column(String(20))
    trigger_ref: Mapped[str] = mapped_column(String(200))
    idempotency_key: Mapped[str] = mapped_column(String(500), index=True)
    status: Mapped[str] = mapped_column(String(20))
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    total_steps: Mapped[int] = mapped_column(Integer, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_workflow_idempotency"),
    )


class WorkflowStep(Base, IdMixin, TimestampMixin):
    """工作流内单步执行记录（通过 run_id 关联租户）。"""
    __tablename__ = "workflow_steps"

    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflow_runs.id"), index=True,
    )
    step_index: Mapped[int] = mapped_column(Integer)
    step_name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    input_summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    output_summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
