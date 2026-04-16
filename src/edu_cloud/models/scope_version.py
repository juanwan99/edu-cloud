"""Scope 版本追踪模型 — 角色/权限变更时版本递增。"""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, TimestampMixin


class ScopeVersion(Base, TimestampMixin):
    """每个 user×school 的 scope 版本号（变更时递增，客户端缓存失效）。"""
    __tablename__ = "scope_versions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    school_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    last_reason: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    __table_args__ = (
        UniqueConstraint("school_id", "user_id", name="uq_scope_school_user"),
    )
