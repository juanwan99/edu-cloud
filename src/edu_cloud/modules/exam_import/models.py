"""外部考试导入会话模型。"""
from sqlalchemy import String, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class ExamImportSession(Base, IdMixin, TimestampMixin):
    __tablename__ = "exam_import_sessions"

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    exam_name: Mapped[str] = mapped_column(String(200))
    exam_type: Mapped[str] = mapped_column(String(20))
    grade_scope: Mapped[str] = mapped_column(String(50))
    import_mode: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    file_path: Mapped[str | None] = mapped_column(String(500), default=None)
    preview_data: Mapped[dict | None] = mapped_column(JSON, default=None)
    mapping_data: Mapped[dict | None] = mapped_column(JSON, default=None)
    result_summary: Mapped[dict | None] = mapped_column(JSON, default=None)
    committed_by: Mapped[str | None] = mapped_column(String(36), default=None)
    exam_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("exams.id"), default=None)
    exam_date: Mapped[str | None] = mapped_column(String(20), default=None)
