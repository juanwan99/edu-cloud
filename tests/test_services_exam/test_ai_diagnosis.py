"""Tests for AI diagnosis service: build_snapshot, caching, schema validation."""
import pytest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from edu_cloud.models.school import School
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.modules.analytics.models import StudentKnpMastery
from edu_cloud.modules.knowledge.models import QuestionKnowledgePoint
from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode
from edu_cloud.modules.analytics.ai_diagnosis_service import (
    build_snapshot, _get_cache, _set_cache, get_or_generate,
)
from edu_cloud.modules.analytics.snapshot_schema import (
    DiagnosisSnapshot, DiagnosisOutput,
)


@pytest.fixture
async def diag_data(db):
    school = School(name="DiagSchool", code="DIAG01")
    db.add(school)
    await db.commit()

    cls = Class(name="一班", grade="七年级", school_id=school.id)
    db.add(cls)
    await db.commit()

    stu1 = Student(name="S1", student_number="D01", class_id=cls.id, school_id=school.id)
    stu2 = Student(name="S2", student_number="D02", class_id=cls.id, school_id=school.id)
    db.add_all([stu1, stu2])
    await db.commit()

    exam = Exam(name="诊断考试", school_id=school.id, exam_date=date(2026, 5, 1), status="published")
    db.add(exam)
    await db.commit()

    subj = Subject(name="数学", code="SX", exam_id=exam.id, school_id=school.id)
    db.add(subj)
    await db.commit()

    q1 = Question(subject_id=subj.id, school_id=school.id, name="Q1", question_type="fill", max_score=10)
    db.add(q1)
    await db.commit()

    node = ConceptGraphNode(
        id="concept_diag_1", name="函数", knowledge_level="L1",
        primary_module="math", synced_at=datetime.now(),
    )
    db.add(node)
    await db.flush()

    db.add(QuestionKnowledgePoint(question_id=q1.id, concept_id=node.id))

    for stu in [stu1, stu2]:
        db.add(StudentAnswer(
            exam_id=exam.id, student_id=stu.id, question_id=q1.id,
            subject_id=subj.id, school_id=school.id, score=5.0,
        ))
        db.add(StudentKnpMastery(
            student_id=stu.id, concept_id=node.id,
            exam_id=exam.id, school_id=school.id, stu_rate=0.5,
        ))

    await db.commit()

    return {
        "school": school, "cls": cls, "exam": exam, "subj": subj,
        "students": [stu1, stu2], "question": q1, "concept": node,
    }


class TestBuildSnapshot:
    @pytest.mark.asyncio
    async def test_builds_valid_snapshot(self, db, diag_data):
        d = diag_data
        snapshot = await build_snapshot(
            db, exam_id=d["exam"].id, school_id=d["school"].id,
            visible_class_ids=[d["cls"].id],
        )
        assert isinstance(snapshot, DiagnosisSnapshot)
        assert snapshot.schema_version == "analytics_class_diagnosis.v1"
        assert snapshot.data_quality.student_count >= 0
        assert snapshot.snapshot.snapshot_hash

    @pytest.mark.asyncio
    async def test_snapshot_with_class_scope(self, db, diag_data):
        d = diag_data
        snapshot = await build_snapshot(
            db, exam_id=d["exam"].id, school_id=d["school"].id,
            class_id=d["cls"].id,
            visible_class_ids=[d["cls"].id],
        )
        assert snapshot.context.school_scope == "class"
        assert snapshot.context.class_id == d["cls"].id

    @pytest.mark.asyncio
    async def test_snapshot_grade_scope_no_class(self, db, diag_data):
        d = diag_data
        snapshot = await build_snapshot(
            db, exam_id=d["exam"].id, school_id=d["school"].id,
            visible_class_ids=[d["cls"].id],
        )
        assert snapshot.context.school_scope == "grade"

    @pytest.mark.asyncio
    async def test_snapshot_includes_knowledge_points(self, db, diag_data):
        d = diag_data
        snapshot = await build_snapshot(
            db, exam_id=d["exam"].id, school_id=d["school"].id,
            subject_id=d["subj"].id,
            visible_class_ids=[d["cls"].id],
        )
        if snapshot.knowledge_points:
            kp = snapshot.knowledge_points[0]
            assert kp.fact_id.startswith("kp:")
            assert kp.concept_id

    @pytest.mark.asyncio
    async def test_snapshot_includes_student_groups(self, db, diag_data):
        d = diag_data
        snapshot = await build_snapshot(
            db, exam_id=d["exam"].id, school_id=d["school"].id,
            visible_class_ids=[d["cls"].id],
        )
        for sg in snapshot.student_groups:
            assert sg.fact_id.startswith("layer:")


class TestCache:
    @pytest.mark.asyncio
    async def test_cache_miss_returns_none(self, db):
        result = await _get_cache(db, "nonexistent_key_12345")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_then_get_cache(self, db):
        test_result = {"summary": {"text": "test"}}
        await _set_cache(
            db, exam_id="e1", school_id="s1", cache_key="test_cache_key_001",
            scope="class", subject_id=None, class_id=None,
            model_version="test-model", result=test_result,
        )
        cached = await _get_cache(db, "test_cache_key_001")
        assert cached is not None
        assert cached["summary"]["text"] == "test"

    @pytest.mark.asyncio
    async def test_expired_cache_returns_none(self, db):
        from sqlalchemy import text as sa_text
        now = datetime.now(timezone.utc)
        expired = now - timedelta(days=1)
        await db.execute(
            sa_text(
                "INSERT INTO ai_diagnosis_cache "
                "(exam_id, school_id, cache_key, scope, prompt_version, model_version, "
                " result_json, created_at, expires_at) "
                "VALUES (:eid, :sid, :ck, :scope, :pv, :mv, :rj, :ca, :ea)"
            ),
            {
                "eid": "e2", "sid": "s2", "ck": "expired_key_002",
                "scope": "class", "pv": "v1", "mv": "",
                "rj": '{"summary":{"text":"old"}}',
                "ca": (now - timedelta(days=10)).isoformat(),
                "ea": expired.isoformat(),
            },
        )
        await db.commit()
        cached = await _get_cache(db, "expired_key_002")
        assert cached is None


MOCK_LLM_RESPONSE = {
    "schema_version": "ai_diagnosis_output.v1",
    "summary": {"text": "整体表现中等", "evidence_fact_ids": ["score:grade_avg"], "confidence": "high"},
    "findings": [{"id": "F1", "text": "函数薄弱", "evidence_fact_ids": ["kp:concept_diag_1"], "confidence": "high"}],
    "risk_alerts": [],
    "teaching_actions": [{"text": "加强函数练习", "target": "全班", "priority": "high", "evidence_fact_ids": ["kp:concept_diag_1"], "confidence": "medium"}],
    "student_followups": [],
    "data_limits": [{"text": "样本量较小", "fact_id": "quality:sample_size", "confidence": "high"}],
}


class TestGetOrGenerate:
    @pytest.mark.asyncio
    async def test_generates_and_caches(self, db, diag_data):
        d = diag_data
        with patch(
            "edu_cloud.modules.analytics.ai_diagnosis_service.generate_diagnosis",
            new_callable=AsyncMock,
            return_value=DiagnosisOutput(**MOCK_LLM_RESPONSE),
        ) as mock_gen:
            result = await get_or_generate(
                db, exam_id=d["exam"].id, school_id=d["school"].id,
                visible_class_ids=[d["cls"].id],
            )
            assert result["summary"]["text"] == "整体表现中等"
            assert mock_gen.call_count == 1

            result2 = await get_or_generate(
                db, exam_id=d["exam"].id, school_id=d["school"].id,
                visible_class_ids=[d["cls"].id],
            )
            assert result2["summary"]["text"] == "整体表现中等"
            assert mock_gen.call_count == 1

    @pytest.mark.asyncio
    async def test_force_refresh_regenerates(self, db, diag_data):
        d = diag_data
        with patch(
            "edu_cloud.modules.analytics.ai_diagnosis_service.generate_diagnosis",
            new_callable=AsyncMock,
            return_value=DiagnosisOutput(**MOCK_LLM_RESPONSE),
        ) as mock_gen:
            await get_or_generate(
                db, exam_id=d["exam"].id, school_id=d["school"].id,
                visible_class_ids=[d["cls"].id],
            )
            assert mock_gen.call_count == 1

            await get_or_generate(
                db, exam_id=d["exam"].id, school_id=d["school"].id,
                visible_class_ids=[d["cls"].id],
                force_refresh=True,
            )
            assert mock_gen.call_count == 2


class TestDiagnosisOutputSchema:
    def test_valid_output(self):
        output = DiagnosisOutput(**MOCK_LLM_RESPONSE)
        assert output.schema_version == "ai_diagnosis_output.v1"
        assert len(output.findings) == 1
        assert output.findings[0].evidence_fact_ids == ["kp:concept_diag_1"]

    def test_minimal_output(self):
        from edu_cloud.modules.analytics.snapshot_schema import DiagnosisOutputItem
        output = DiagnosisOutput(
            summary=DiagnosisOutputItem(text="ok", evidence_fact_ids=[], confidence="low"),
        )
        assert output.findings == []
        assert output.data_limits == []
