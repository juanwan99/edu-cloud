"""题目-知识点关联（统一到 ConceptGraphNode ID 体系）。"""
from sqlalchemy import String, Boolean, UniqueConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin

GLOBAL_SCHOOL_ID = "__GLOBAL__"


class QuestionKnowledgePoint(Base, IdMixin, TimestampMixin):
    __tablename__ = "question_knowledge_points"
    __table_args__ = (UniqueConstraint("question_id", "concept_id"),)

    question_id: Mapped[str] = mapped_column(String(36), ForeignKey("questions.id"), index=True)
    concept_id: Mapped[str] = mapped_column(String(64), ForeignKey("concept_graph_nodes.id"), index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
