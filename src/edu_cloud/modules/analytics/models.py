from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, JSON, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import NUMERIC
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from edu_cloud.models.base import Base


class ClassAnalysis(Base):
    __tablename__ = "class_analysis"
    __table_args__ = (
        UniqueConstraint("exam_id", "subject_id", "class_id", name="uq_class_analysis"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id"), nullable=False, index=True)
    subject_id: Mapped[str] = mapped_column(String(36), ForeignKey("subjects.id"), nullable=False, index=True)
    class_id: Mapped[str] = mapped_column(String(36), ForeignKey("classes.id"), nullable=False, index=True)
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), nullable=False, index=True)
    avg_score = Column(NUMERIC(6, 2))
    max_score = Column(NUMERIC(6, 2))
    min_score = Column(NUMERIC(6, 2))
    pass_rate = Column(NUMERIC(5, 2))
    excellent_rate = Column(NUMERIC(5, 2))
    student_count = Column(Integer)
    score_distribution = Column(JSON)
    common_wrong_questions = Column(JSON)
    knowledge_mastery = Column(JSON)
    computed_at = Column(DateTime(timezone=True), server_default=func.now())


class StudentAnalysis(Base):
    __tablename__ = "student_analysis"
    __table_args__ = (
        UniqueConstraint("student_id", "exam_id", name="uq_student_analysis"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(String(36), ForeignKey("students.id"), nullable=False, index=True)
    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id"), nullable=False, index=True)
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), nullable=False, index=True)
    total_score = Column(NUMERIC(7, 2))
    rank_in_class = Column(Integer)
    rank_in_grade = Column(Integer)
    subject_scores = Column(JSON)
    weak_knowledge = Column(JSON)
    improvement_trend = Column(JSON)
    computed_at = Column(DateTime(timezone=True), server_default=func.now())


class StudentKnpMastery(Base):
    __tablename__ = "student_knp_mastery"
    __table_args__ = (
        UniqueConstraint("student_id", "exam_id", "concept_id", name="uq_student_knp_mastery"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(String(36), ForeignKey("students.id"), nullable=False, index=True)
    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id"), nullable=False, index=True)
    concept_id: Mapped[str] = mapped_column(String(64), ForeignKey("concept_graph_nodes.id"), nullable=False)
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), nullable=False, index=True)
    stu_rate = Column(NUMERIC(4, 3))
    class_rate = Column(NUMERIC(4, 3))
    grade_rate = Column(NUMERIC(4, 3))


class AiDiagnosisCache(Base):
    __tablename__ = "ai_diagnosis_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exam_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    school_id: Mapped[str] = mapped_column(String(64), nullable=False)
    cache_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False, server_default="class")
    subject_id = mapped_column(String(64), nullable=True)
    class_id = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False, server_default="v1")
    model_version: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")
    result_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
