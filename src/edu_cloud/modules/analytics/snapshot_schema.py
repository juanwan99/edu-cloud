"""AI diagnosis snapshot schema -- input/output Pydantic models for LLM-based diagnosis."""

import hashlib
import json
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Input snapshot (assembled from exam data, fed to LLM)
# ---------------------------------------------------------------------------

class DiagnosisContext(BaseModel):
    school_scope: str
    exam_id: str
    exam_name: str
    exam_date: str  # ISO8601
    grade_id: Optional[str] = None
    class_id: Optional[str] = None
    subject_code: Optional[str] = None
    user_role: str


class SnapshotMeta(BaseModel):
    snapshot_hash: str
    generated_at: str  # ISO8601
    score_policy: str = "confirmed > ai_done > human > scan"


class DataQuality(BaseModel):
    student_count: int
    scored_count: int
    missing_count: int = 0
    knowledge_mapping_coverage: float = 0.0  # 0-1
    low_evidence_concepts: list[str] = Field(default_factory=list)


class ScoreSummary(BaseModel):
    full_score: float
    avg: float
    median: float
    stddev: float
    pass_rate: float  # 0-1
    excellent_rate: float  # 0-1
    segments: list[dict] = Field(default_factory=list)  # [{label, count}]


class ComparisonData(BaseModel):
    grade_avg: Optional[float] = None
    class_avg_delta: Optional[float] = None
    class_rank_in_grade: Optional[int] = None
    parallel_class_count: Optional[int] = None
    previous_exam_avg_delta: Optional[float] = None


class KnowledgePoint(BaseModel):
    fact_id: str  # format: "kp:{concept_id}"
    concept_id: str
    name: str
    class_rate: float  # 0-1
    grade_rate: Optional[float] = None
    gap_to_grade: Optional[float] = None
    unmastered_student_count: int = 0
    question_ids: list[str] = Field(default_factory=list)
    evidence_level: str = "medium"  # high/medium/low


class StudentGroup(BaseModel):
    fact_id: str  # format: "layer:{label}"
    label: str  # e.g. excellent / good / needs_improvement
    count: int
    avg: Optional[float] = None
    avg_score_rate: Optional[float] = None
    weak_concepts: list[str] = Field(default_factory=list)


class DiagnosisConstraints(BaseModel):
    max_findings: int = 5
    max_actions: int = 6
    forbid_unbacked_claims: bool = True
    hide_student_names: bool = True


class DiagnosisSnapshot(BaseModel):
    schema_version: str = "analytics_class_diagnosis.v1"
    context: DiagnosisContext
    snapshot: SnapshotMeta
    data_quality: DataQuality
    score_summary: ScoreSummary
    comparison: ComparisonData = Field(default_factory=ComparisonData)
    knowledge_points: list[KnowledgePoint] = Field(default_factory=list)
    student_groups: list[StudentGroup] = Field(default_factory=list)
    constraints: DiagnosisConstraints = Field(default_factory=DiagnosisConstraints)


# ---------------------------------------------------------------------------
# Snapshot hash computation
# ---------------------------------------------------------------------------

def compute_snapshot_hash(
    exam_id: str,
    school_id: str,
    scope: str,
    subject_id: str | None,
    class_id: str | None,
    score_version: str,
    knowledge_version: str,
    filters_hash: str = "",
) -> str:
    """Compute a deterministic hash from input parameters."""
    parts = [
        exam_id, school_id, scope,
        subject_id or "", class_id or "",
        score_version, knowledge_version, filters_hash,
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# LLM output schema (used to validate structured LLM responses)
# ---------------------------------------------------------------------------

class DiagnosisOutputItem(BaseModel):
    text: str
    evidence_fact_ids: list[str] = Field(default_factory=list)
    confidence: str = "medium"  # high/medium/low


class DiagnosisFinding(DiagnosisOutputItem):
    id: str  # F1, F2, ...


class TeachingAction(DiagnosisOutputItem):
    target: Optional[str] = None
    priority: str = "medium"


class StudentFollowup(DiagnosisOutputItem):
    layer: Optional[str] = None


class DataLimit(BaseModel):
    text: str
    fact_id: str
    confidence: str = "high"


class DiagnosisOutput(BaseModel):
    schema_version: str = "ai_diagnosis_output.v1"
    summary: DiagnosisOutputItem
    findings: list[DiagnosisFinding] = Field(default_factory=list)
    risk_alerts: list[DiagnosisOutputItem] = Field(default_factory=list)
    teaching_actions: list[TeachingAction] = Field(default_factory=list)
    student_followups: list[StudentFollowup] = Field(default_factory=list)
    data_limits: list[DataLimit] = Field(default_factory=list)
