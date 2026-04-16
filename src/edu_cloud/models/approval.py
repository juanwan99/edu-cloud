from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class ApprovalFlow(Base, IdMixin, TimestampMixin):
    __tablename__ = "approval_flows"

    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id"), nullable=False
    )
    chain_type: Mapped[str] = mapped_column(String(50), nullable=False)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")


class ApprovalStep(Base, IdMixin, TimestampMixin):
    __tablename__ = "approval_steps"

    flow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("approval_flows.id"), nullable=False
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    approver_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="waiting")
    comment: Mapped[str | None] = mapped_column(Text, default=None)
    acted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
