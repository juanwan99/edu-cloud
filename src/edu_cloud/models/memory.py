"""Cross-session memory models: EntityMemory + ProjectState."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import JSON, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class EntityMemory(Base, IdMixin, TimestampMixin):
    """Persistent entity profile (student/teacher/class/session_episode)."""

    __tablename__ = "entity_memory"

    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[str] = mapped_column(String(36))
    school_id: Mapped[str] = mapped_column(String(36))
    facts: Mapped[dict] = mapped_column(JSON, default=dict)

    __table_args__ = (
        Index("ix_entity_memory_lookup", "school_id", "entity_type", "entity_id"),
        UniqueConstraint("school_id", "entity_type", "entity_id", name="uq_entity_memory_lookup"),
    )


class ProjectState(Base, IdMixin, TimestampMixin):
    """Multi-session project progress."""

    __tablename__ = "project_state"

    project_type: Mapped[str] = mapped_column(String(30))
    project_id: Mapped[str] = mapped_column(String(36))
    owner_id: Mapped[str] = mapped_column(String(36))
    school_id: Mapped[str] = mapped_column(String(36))
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    checkpoints: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    status: Mapped[Optional[str]] = mapped_column(String(20), default="active")

    def __init__(self, **kwargs: object) -> None:
        if "status" not in kwargs:
            kwargs["status"] = "active"
        if "checkpoints" not in kwargs:
            kwargs["checkpoints"] = []
        super().__init__(**kwargs)

    __table_args__ = (
        Index("ix_project_state_owner", "owner_id", "school_id"),
        Index("ix_project_state_lookup", "project_type", "project_id"),
        UniqueConstraint("project_type", "project_id", name="uq_project_state_project"),
    )
