"""Tests for analytics snapshot schema (input + output)."""

import pytest

from edu_cloud.modules.analytics.snapshot_schema import (
    ComparisonData,
    DataQuality,
    DiagnosisConstraints,
    DiagnosisContext,
    DiagnosisFinding,
    DiagnosisOutput,
    DiagnosisOutputItem,
    DiagnosisSnapshot,
    KnowledgePoint,
    ScoreSummary,
    SnapshotMeta,
    StudentFollowup,
    StudentGroup,
    TeachingAction,
    compute_snapshot_hash,
)


# -- helpers ----------------------------------------------------------------

def _make_context(**overrides):
    defaults = dict(
        school_scope="school",
        exam_id="exam-001",
        exam_name="期中考试",
        exam_date="2026-05-01T00:00:00+08:00",
        user_role="academic_director",
    )
    defaults.update(overrides)
    return DiagnosisContext(**defaults)


def _make_snapshot_meta(**overrides):
    defaults = dict(
        snapshot_hash="abc123",
        generated_at="2026-05-01T12:00:00+08:00",
    )
    defaults.update(overrides)
    return SnapshotMeta(**defaults)


def _make_data_quality(**overrides):
    defaults = dict(student_count=40, scored_count=38)
    defaults.update(overrides)
    return DataQuality(**defaults)


def _make_score_summary(**overrides):
    defaults = dict(
        full_score=150.0,
        avg=110.5,
        median=112.0,
        stddev=15.3,
        pass_rate=0.85,
        excellent_rate=0.30,
    )
    defaults.update(overrides)
    return ScoreSummary(**defaults)


# -- 1. DiagnosisSnapshot full build ----------------------------------------

class TestDiagnosisSnapshotBuild:
    def test_full_build(self):
        """DiagnosisSnapshot builds with all fields populated."""
        snap = DiagnosisSnapshot(
            context=_make_context(),
            snapshot=_make_snapshot_meta(),
            data_quality=_make_data_quality(),
            score_summary=_make_score_summary(
                segments=[{"label": "优秀", "count": 12}],
            ),
            comparison=ComparisonData(
                grade_avg=105.0,
                class_avg_delta=5.5,
                class_rank_in_grade=2,
                parallel_class_count=8,
            ),
            knowledge_points=[
                KnowledgePoint(
                    fact_id="kp:c001",
                    concept_id="c001",
                    name="函数的概念",
                    class_rate=0.65,
                    grade_rate=0.70,
                    gap_to_grade=-0.05,
                    unmastered_student_count=14,
                    question_ids=["q1", "q5"],
                    evidence_level="high",
                ),
            ],
            student_groups=[
                StudentGroup(
                    fact_id="layer:excellent",
                    label="优秀",
                    count=12,
                    avg=135.0,
                    avg_score_rate=0.90,
                    weak_concepts=["c003"],
                ),
            ],
            constraints=DiagnosisConstraints(max_findings=3),
        )

        assert snap.schema_version == "analytics_class_diagnosis.v1"
        assert snap.context.exam_id == "exam-001"
        assert snap.score_summary.avg == 110.5
        assert len(snap.knowledge_points) == 1
        assert snap.knowledge_points[0].fact_id == "kp:c001"
        assert len(snap.student_groups) == 1
        assert snap.constraints.max_findings == 3

    def test_default_fields(self):
        """Defaults are applied for optional / default_factory fields."""
        snap = DiagnosisSnapshot(
            context=_make_context(),
            snapshot=_make_snapshot_meta(),
            data_quality=_make_data_quality(),
            score_summary=_make_score_summary(),
        )

        assert snap.comparison.grade_avg is None
        assert snap.knowledge_points == []
        assert snap.student_groups == []
        assert snap.constraints.max_findings == 5
        assert snap.constraints.forbid_unbacked_claims is True


# -- 2. zero-data scenario -------------------------------------------------

class TestZeroDataSnapshot:
    def test_zero_students(self):
        """Snapshot with zero students is valid."""
        snap = DiagnosisSnapshot(
            context=_make_context(),
            snapshot=_make_snapshot_meta(),
            data_quality=DataQuality(student_count=0, scored_count=0),
            score_summary=ScoreSummary(
                full_score=100.0, avg=0.0, median=0.0,
                stddev=0.0, pass_rate=0.0, excellent_rate=0.0,
            ),
        )
        assert snap.data_quality.student_count == 0
        assert snap.knowledge_points == []
        assert snap.student_groups == []

    def test_no_knowledge_points(self):
        """Snapshot without knowledge points is valid."""
        snap = DiagnosisSnapshot(
            context=_make_context(),
            snapshot=_make_snapshot_meta(),
            data_quality=_make_data_quality(knowledge_mapping_coverage=0.0),
            score_summary=_make_score_summary(),
        )
        assert snap.data_quality.knowledge_mapping_coverage == 0.0
        assert snap.knowledge_points == []


# -- 3. KnowledgePoint fact_id format ---------------------------------------

class TestKnowledgePointFactId:
    def test_valid_kp_prefix(self):
        kp = KnowledgePoint(
            fact_id="kp:concept_abc",
            concept_id="concept_abc",
            name="导数",
            class_rate=0.72,
        )
        assert kp.fact_id.startswith("kp:")

    def test_fact_id_without_prefix_still_constructs(self):
        """fact_id is a plain string -- prefix is a convention, not enforced by Pydantic."""
        kp = KnowledgePoint(
            fact_id="no_prefix",
            concept_id="x",
            name="test",
            class_rate=0.5,
        )
        assert not kp.fact_id.startswith("kp:")


# -- 4 & 5. compute_snapshot_hash determinism & variance --------------------

class TestComputeSnapshotHash:
    _ARGS = dict(
        exam_id="e1", school_id="s1", scope="class",
        subject_id="math", class_id="c1",
        score_version="v1", knowledge_version="v1",
    )

    def test_deterministic(self):
        h1 = compute_snapshot_hash(**self._ARGS)
        h2 = compute_snapshot_hash(**self._ARGS)
        assert h1 == h2
        assert len(h1) == 16

    def test_different_inputs(self):
        h1 = compute_snapshot_hash(**self._ARGS)
        h2 = compute_snapshot_hash(**{**self._ARGS, "exam_id": "e2"})
        assert h1 != h2

    def test_none_subject_id(self):
        h1 = compute_snapshot_hash(**{**self._ARGS, "subject_id": None})
        h2 = compute_snapshot_hash(**self._ARGS)
        assert h1 != h2

    def test_filters_hash_affects_result(self):
        h1 = compute_snapshot_hash(**self._ARGS, filters_hash="")
        h2 = compute_snapshot_hash(**self._ARGS, filters_hash="abc")
        assert h1 != h2


# -- 6. DiagnosisOutput parse -----------------------------------------------

class TestDiagnosisOutputParse:
    def test_parse_llm_json(self):
        """DiagnosisOutput can parse a typical LLM JSON response."""
        raw = {
            "schema_version": "ai_diagnosis_output.v1",
            "summary": {
                "text": "本次考试整体表现良好",
                "evidence_fact_ids": ["kp:c001"],
                "confidence": "high",
            },
            "findings": [
                {
                    "id": "F1",
                    "text": "函数掌握率偏低",
                    "evidence_fact_ids": ["kp:c001"],
                    "confidence": "high",
                },
                {
                    "id": "F2",
                    "text": "优秀生比例下降",
                    "evidence_fact_ids": ["layer:excellent"],
                },
            ],
            "risk_alerts": [
                {"text": "样本量不足", "evidence_fact_ids": [], "confidence": "low"},
            ],
            "teaching_actions": [
                {
                    "text": "针对函数概念加强训练",
                    "evidence_fact_ids": ["kp:c001"],
                    "target": "全班",
                    "priority": "high",
                },
            ],
            "student_followups": [
                {
                    "text": "待提升层学生需个别辅导",
                    "evidence_fact_ids": ["layer:needs_improvement"],
                    "layer": "needs_improvement",
                },
            ],
            "data_limits": [
                {
                    "text": "知识点覆盖率仅 40%",
                    "fact_id": "kp:coverage",
                    "confidence": "high",
                },
            ],
        }

        output = DiagnosisOutput(**raw)

        assert output.schema_version == "ai_diagnosis_output.v1"
        assert output.summary.text == "本次考试整体表现良好"
        assert len(output.findings) == 2
        assert output.findings[0].id == "F1"
        assert len(output.teaching_actions) == 1
        assert output.teaching_actions[0].priority == "high"
        assert len(output.student_followups) == 1
        assert output.student_followups[0].layer == "needs_improvement"
        assert len(output.data_limits) == 1

    def test_minimal_output(self):
        """DiagnosisOutput with only required summary field."""
        output = DiagnosisOutput(
            summary=DiagnosisOutputItem(text="无异常"),
        )
        assert output.findings == []
        assert output.risk_alerts == []
        assert output.teaching_actions == []
        assert output.student_followups == []
        assert output.data_limits == []


# -- 7. evidence_fact_ids field presence ------------------------------------

class TestEvidenceFactIds:
    def test_output_item_has_evidence_field(self):
        item = DiagnosisOutputItem(text="test")
        assert hasattr(item, "evidence_fact_ids")
        assert item.evidence_fact_ids == []

    def test_finding_has_evidence_field(self):
        f = DiagnosisFinding(id="F1", text="test")
        assert hasattr(f, "evidence_fact_ids")
        assert f.evidence_fact_ids == []

    def test_teaching_action_has_evidence_field(self):
        a = TeachingAction(text="do something")
        assert hasattr(a, "evidence_fact_ids")
        assert a.evidence_fact_ids == []

    def test_student_followup_has_evidence_field(self):
        s = StudentFollowup(text="follow up")
        assert hasattr(s, "evidence_fact_ids")
        assert s.evidence_fact_ids == []
