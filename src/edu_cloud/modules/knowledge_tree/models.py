"""知识树图谱 — 投影自 knowledge.db 的概念和关系。"""

from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, Text, ForeignKey, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base


class ConceptGraphNode(Base):
    """概念图谱节点（投影自 knowledge.db concepts + big_concepts）"""
    __tablename__ = "concept_graph_nodes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    knowledge_level: Mapped[str] = mapped_column(String(10), nullable=False)
    primary_module: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # 层级重构新增列
    subject: Mapped[str | None] = mapped_column(String(30))
    course_code: Mapped[str | None] = mapped_column(String(10), default=None, index=True)
    node_type: Mapped[str] = mapped_column(String(20), default="concept")  # concept | big_concept
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    review_status: Mapped[str | None] = mapped_column(String(20))
    reviewed_by: Mapped[str | None] = mapped_column(String(100))
    reviewed_at: Mapped[str | None] = mapped_column(String(30))
    aliases_json: Mapped[str | None] = mapped_column(Text)
    evidence_ids_json: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[int | None] = mapped_column(Integer)
    bloom_level: Mapped[str | None] = mapped_column(String(20))


class ConceptBigConceptMap(Base):
    """BigConcept→Concept 映射（投影自 knowledge.db concept_big_concept_map）"""
    __tablename__ = "concept_big_concept_map"

    concept_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("concept_graph_nodes.id"), primary_key=True
    )
    big_concept_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("concept_graph_nodes.id"), primary_key=True
    )
    is_primary: Mapped[bool] = mapped_column(default=False)


class ConceptGraphEdge(Base):
    """概念图谱边（投影自 knowledge.db concept_relations）"""
    __tablename__ = "concept_graph_edges"
    __table_args__ = (
        UniqueConstraint("source_id", "target_id", "relation_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("concept_graph_nodes.id"), nullable=False, index=True
    )
    target_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("concept_graph_nodes.id"), nullable=False, index=True
    )
    relation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    strength: Mapped[float] = mapped_column(Float, default=1.0)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    evidence: Mapped[str | None] = mapped_column(Text, default=None)
    pedagogical_use: Mapped[str | None] = mapped_column(String(30), default=None)
    review_status: Mapped[str] = mapped_column(String(20), default="ai_draft")
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class EditSyncFailure(Base):
    """编辑回写失败记录。"""
    __tablename__ = "edit_sync_failures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operation_json: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ConceptStats(Base):
    """概念统计指标（从 knowledge.db + MCU 计算投影）。

    Graph API 返回节点时合并这些指标，让前端按重要度/考频可视化。
    计算时机：sync 同步后全量计算；编辑图谱时增量计算受影响节点。
    """
    __tablename__ = "concept_stats"

    concept_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("concept_graph_nodes.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    exam_frequency: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    exam_coverage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_difficulty: Mapped[float | None] = mapped_column(Float)
    importance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    planning_weight: Mapped[dict | None] = mapped_column(JSON)
    textbook_chapters: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    study_unit_id: Mapped[str | None] = mapped_column(String(64))
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    prerequisite_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    computed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
