"""Knowledge 模块模型 — 知识点（从 exam-ai models/curriculum.py 迁入）。"""
from sqlalchemy import String, Integer, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin

GLOBAL_SCHOOL_ID = "__GLOBAL__"


class KnowledgePoint(Base, IdMixin, TimestampMixin):
    __tablename__ = "knowledge_points"

    code: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(200))
    course_code: Mapped[str | None] = mapped_column(String(50), default=None)
    parent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("knowledge_points.id"), default=None, index=True)
    level: Mapped[int | None] = mapped_column(Integer, default=None)
    description: Mapped[str | None] = mapped_column(String(500), default=None)
    grade_hint: Mapped[str | None] = mapped_column(String(50), default=None)
    school_id: Mapped[str] = mapped_column(String(50), default="__GLOBAL__")
    embedding: Mapped[str | None] = mapped_column(String(2000), default=None)


class QuestionKnowledgePoint(Base, IdMixin, TimestampMixin):
    __tablename__ = "question_knowledge_points"
    __table_args__ = (UniqueConstraint("question_id", "knowledge_point_id"),)

    question_id: Mapped[str] = mapped_column(String(36), ForeignKey("questions.id"))
    knowledge_point_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_points.id"))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
