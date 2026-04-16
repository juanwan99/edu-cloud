from sqlalchemy import String, Float, Integer, Boolean, JSON, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class AnswerLog(Base, IdMixin, TimestampMixin):
    """作答日志 — 唯一事实源"""
    __tablename__ = "answer_logs"
    __table_args__ = (UniqueConstraint("school_id", "exam_id", "student_id", "question_id"),)

    student_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    question_id: Mapped[str | None] = mapped_column(String(36))
    exam_id: Mapped[str | None] = mapped_column(String(36))
    da_ids: Mapped[dict] = mapped_column(JSON, nullable=False)
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score_rate: Mapped[float | None] = mapped_column(Float)
    elapsed_ms: Mapped[int | None] = mapped_column(Integer)
    source_type: Mapped[str | None] = mapped_column(String(20))
    school_id: Mapped[str | None] = mapped_column(String(36), index=True)


class StudentDaMastery(Base, IdMixin, TimestampMixin):
    """DA 级掌握度 — BKT 主状态"""
    __tablename__ = "student_da_mastery"
    __table_args__ = (UniqueConstraint("school_id", "student_id", "da_id"),)

    student_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    da_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    mastery_prob: Mapped[float] = mapped_column(Float, default=0.1)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    last_answer_at: Mapped[DateTime | None] = mapped_column(DateTime)
    school_id: Mapped[str | None] = mapped_column(String(36), index=True)


class DaBktParams(Base):
    """DA 默认 BKT 参数（per-DA，非 per-student）"""
    __tablename__ = "da_bkt_params"

    da_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    p_init: Mapped[float] = mapped_column(Float, default=0.1)
    p_transit: Mapped[float] = mapped_column(Float, default=0.2)
    p_guess: Mapped[float] = mapped_column(Float, default=0.25)
    p_slip: Mapped[float] = mapped_column(Float, default=0.1)
    source: Mapped[str] = mapped_column(String(20), default="expert")


class DaKnowledgePointMap(Base):
    """DA 与知识点映射"""
    __tablename__ = "da_knowledge_point_map"

    da_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    knowledge_point_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)


class QuestionDaOverride(Base, TimestampMixin):
    """题目 DA 人工覆盖"""
    __tablename__ = "question_da_override"

    question_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    da_ids: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(100))


class AdaptiveCard(Base, IdMixin, TimestampMixin):
    """FSRS 复习卡片（V1）"""
    __tablename__ = "adaptive_cards"
    __table_args__ = (UniqueConstraint("student_id", "da_id"),)

    student_id: Mapped[str] = mapped_column(String(100), nullable=False)
    da_id: Mapped[str] = mapped_column(String(100), nullable=False)
    stability: Mapped[float | None] = mapped_column(Float)
    difficulty: Mapped[float | None] = mapped_column(Float)
    due_date: Mapped[DateTime | None] = mapped_column(DateTime)
    last_review: Mapped[DateTime | None] = mapped_column(DateTime)


class DaCatalogSnapshot(Base):
    """DA 目录快照（本地投影，定期从 knowledge.db 同步）"""
    __tablename__ = "da_catalog_snapshot"

    da_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(200))
    module: Mapped[str | None] = mapped_column(String(10))
    concept_ids: Mapped[dict | None] = mapped_column(JSON)
    study_unit_ids: Mapped[dict | None] = mapped_column(JSON)
    synced_at: Mapped[DateTime | None] = mapped_column(DateTime)
