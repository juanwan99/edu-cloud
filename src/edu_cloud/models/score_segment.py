# DEPRECATED: 未使用的模型，保留仅因 alembic 迁移创建了对应表。
# 正式删除需先写 DROP TABLE 迁移。
from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TenantMixin, TimestampMixin


class ScoreSegmentConfig(Base, IdMixin, TenantMixin, TimestampMixin):
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
        String(36), ForeignKey("users.id"), nullable=True, index=True,
    )
