"""Card 模块模型 — Template + CardSkeleton（从 exam-ai models/exam.py 提取）。"""
from sqlalchemy import String, Integer, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class Template(Base, IdMixin, TimestampMixin):
    __tablename__ = "templates"
    __table_args__ = (UniqueConstraint("subject_id", "side"),)

    subject_id: Mapped[str] = mapped_column(String(36), ForeignKey("subjects.id"), index=True)
    side: Mapped[str] = mapped_column(String(1))  # A / B
    image_width: Mapped[int] = mapped_column(Integer, default=0)
    image_height: Mapped[int] = mapped_column(Integer, default=0)
    anchors: Mapped[list | None] = mapped_column(JSON, default=None)
    regions: Mapped[list | None] = mapped_column(JSON, default=None)
    sample_image: Mapped[str | None] = mapped_column(String(500), default=None)
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)


class CardSkeleton(Base, IdMixin, TimestampMixin):
    __tablename__ = "card_skeletons"
    __table_args__ = (UniqueConstraint("school_id", "subject_code"),)

    subject_code: Mapped[str] = mapped_column(String(50))
    paper_size: Mapped[str] = mapped_column(String(10), default="A3")
    skeleton_data: Mapped[dict] = mapped_column(JSON, default=dict)
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
