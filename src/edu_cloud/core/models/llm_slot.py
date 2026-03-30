"""LLM 模型槽位配置 — 支持平台默认 + 学校覆盖。"""

from sqlalchemy import String, Integer, Boolean, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class LLMSlot(Base, IdMixin, TimestampMixin):
    """LLM 模型槽位。school_id=NULL 为平台默认，有值为学校覆盖。"""
    __tablename__ = "llm_slots"
    __table_args__ = (UniqueConstraint("school_id", "slot_number"),)

    school_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("schools.id"), default=None, index=True
    )
    slot_number: Mapped[int] = mapped_column(Integer)  # 1-6
    api_url: Mapped[str] = mapped_column(String(500))
    api_key: Mapped[str] = mapped_column(String(500))
    model: Mapped[str] = mapped_column(String(100))
    label: Mapped[str | None] = mapped_column(String(100), default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    tier: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
