from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class Document(Base, IdMixin, TimestampMixin):
    __tablename__ = "documents"

    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    content_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    content_html: Mapped[str | None] = mapped_column(Text, default=None)
    pdf_url: Mapped[str | None] = mapped_column(String, default=None)
    source_context: Mapped[dict | None] = mapped_column(JSON, default=None)
    ai_session_id: Mapped[str | None] = mapped_column(String, default=None)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    assigned_to: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), default=None, nullable=True
    )
    approved_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), default=None
    )
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    execution_result: Mapped[dict | None] = mapped_column(JSON, default=None)
    version: Mapped[int] = mapped_column(Integer, default=1)
    school_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("schools.id"), nullable=False
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("status", "draft")
        kwargs.setdefault("version", 1)
        super().__init__(**kwargs)


class DocumentVersion(Base, IdMixin, TimestampMixin):
    __tablename__ = "document_versions"

    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    edited_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    change_summary: Mapped[str | None] = mapped_column(String(500), default=None)
