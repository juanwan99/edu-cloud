"""分数段配置模型。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TenantMixin, TimestampMixin


class ScoreSegmentConfig(Base, IdMixin, TenantMixin, TimestampMixin):
    """学校级分数段配置（per school + optional per subject override）。

    Uniqueness (one default per school, one per school+subject) is enforced by:
    - Service-layer upsert logic (all backends)
    - Partial unique indexes added in the Alembic migration (PostgreSQL only)

    The partial indexes use ``postgresql_where`` which SQLite cannot represent,
    so they are kept out of the ORM model to avoid SQLite creating plain unique
    indexes that break multi-row inserts in tests.
    """
    __tablename__ = "score_segment_config"

    subject_code: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, default=None,
    )
    boundaries: Mapped[list] = mapped_column(
        JSON, default=lambda: [85, 70, 60],
    )
    labels: Mapped[list] = mapped_column(
        JSON, default=lambda: ["优秀", "良好", "及格", "不及格"],
    )
    created_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True,
    )
