from sqlalchemy import String, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class AuditLog(Base, IdMixin, TimestampMixin):
    """实体变更审计日志。"""
    __tablename__ = "audit_logs"

    school_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("schools.id"), index=True, default=None, nullable=True,
    )
    # F-02 fix: nullable — 无 user context 时写 None 而非 "-"
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, default=None, nullable=True,
    )
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(20))
    before_data: Mapped[dict | None] = mapped_column(JSON, default=None, nullable=True)
    after_data: Mapped[dict | None] = mapped_column(JSON, default=None, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(50), default=None, nullable=True)
