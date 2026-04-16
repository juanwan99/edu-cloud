"""Tests for W1 domain tools: exam_overview, class_report, student_diagnosis."""
import pytest
from types import SimpleNamespace

from edu_cloud.ai.tool_context import ToolContext, ToolResult
from edu_cloud.models.agent_snapshot import ExamAnalysisSnapshot, ClassExamReport
from edu_cloud.models.school import School
from edu_cloud.modules.exam.models import Exam
from edu_cloud.modules.profile.models import StudentExamSnapshot


def _ctx(db, school_id, role="principal", user_id="u1", class_ids=None):
    return ToolContext(db=db, school_id=school_id, user_id=user_id, role=role, class_ids=class_ids)


@pytest.fixture
async def seeded_snapshots(db):
    school = School(name="工具测试校", code="TOOLTEST", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    exam = Exam(name="测试考试", school_id=school.id, semester="2025-2026-2")
    db.add(exam)
    await db.flush()

    # School overview snapshot
    db.add(ExamAnalysisSnapshot(
        exam_id=exam.id, school_id=school.id,
        snapshot_type="school_overview", target_type="school",
        semester="2025-2026-2", version=1, status="ready",
        metrics={"avg_score": 78.5, "max_score": 99, "total_students": 30},
    ))

    # Subject breakdown snapshot
    db.add(ExamAnalysisSnapshot(
        exam_id=exam.id, school_id=school.id,
        snapshot_type="subject_detail", target_type="subject",
        target_id=None, subject_code="SX",
        semester="2025-2026-2", version=1, status="ready",
        metrics={"avg_score": 80.0, "max_score": 100, "total_students": 30},
    ))

    # Class report
    db.add(ClassExamReport(
        exam_id=exam.id, class_id="class-1", school_id=school.id,
        grade_rank=1, class_avg=82.0, grade_avg=78.5,
        metrics={"top_students": 5}, version=1, status="ready",
    ))

    # Student exam snapshot
    db.add(StudentExamSnapshot(
        student_id="stu-1", exam_id=exam.id, subject_code="SX",
        total_score=92.0, max_score=100.0, score_rate=0.92,
        class_rank=1, grade_rank=3, class_size=40, grade_size=300,
        knowledge_scores={"algebra": 0.95, "geometry": 0.88},
        error_summary={"careless": 1, "concept": 0},
        school_id=school.id,
    ))

    await db.commit()
    return SimpleNamespace(exam_id=exam.id, school_id=school.id)


# ── get_exam_overview ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_exam_overview_reads_snapshot(db, seeded_snapshots):
    from edu_cloud.ai.tools.exam_overview import get_exam_overview

    result = await get_exam_overview(
        {"exam_id": seeded_snapshots.exam_id},
        _ctx(db, seeded_snapshots.school_id),
    )
    assert result.success
    assert result.data["status"] == "ready"
    assert result.data["school_overview"]["avg_score"] == 78.5
    assert len(result.data["subject_breakdowns"]) == 1
    assert result.data["subject_breakdowns"][0]["subject_code"] == "SX"


@pytest.mark.asyncio
async def test_get_exam_overview_no_snapshot(db, seeded_snapshots):
    from edu_cloud.ai.tools.exam_overview import get_exam_overview

    result = await get_exam_overview(
        {"exam_id": "nonexistent-exam"},
        _ctx(db, seeded_snapshots.school_id),
    )
    assert result.success
    assert result.data["status"] == "not_found"


# ── get_class_report ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_class_report_returns_stats(db, seeded_snapshots):
    from edu_cloud.ai.tools.class_report_tool import get_class_report

    result = await get_class_report(
        {"exam_id": seeded_snapshots.exam_id, "class_id": "class-1"},
        _ctx(db, seeded_snapshots.school_id),
    )
    assert result.success
    assert result.data["class_avg"] == 82.0
    assert result.data["grade_rank"] == 1
    assert result.data["grade_avg"] == 78.5
    assert result.data["vs_grade_avg"] == pytest.approx(3.5)


@pytest.mark.asyncio
async def test_get_class_report_not_found(db, seeded_snapshots):
    from edu_cloud.ai.tools.class_report_tool import get_class_report

    result = await get_class_report(
        {"exam_id": seeded_snapshots.exam_id, "class_id": "nonexistent"},
        _ctx(db, seeded_snapshots.school_id),
    )
    assert result.success
    assert result.data["status"] == "not_found"


# ── get_student_diagnosis ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_student_diagnosis_returns_profile(db, seeded_snapshots):
    from edu_cloud.ai.tools.student_diagnosis import get_student_diagnosis

    result = await get_student_diagnosis(
        {"student_id": "stu-1", "exam_id": seeded_snapshots.exam_id},
        _ctx(db, seeded_snapshots.school_id, role="parent"),
    )
    assert result.success
    assert result.data["score_rate"] == 0.92
    assert result.data["class_rank"] == 1
    assert result.data["grade_rank"] == 3
    assert result.data["knowledge_scores"]["algebra"] == 0.95
    assert result.data["error_summary"]["careless"] == 1


@pytest.mark.asyncio
async def test_get_student_diagnosis_no_exam_id(db, seeded_snapshots):
    """Without exam_id, returns the latest snapshot for the student."""
    from edu_cloud.ai.tools.student_diagnosis import get_student_diagnosis

    result = await get_student_diagnosis(
        {"student_id": "stu-1"},
        _ctx(db, seeded_snapshots.school_id, role="parent"),
    )
    assert result.success
    assert result.data["score_rate"] == 0.92


@pytest.mark.asyncio
async def test_get_student_diagnosis_not_found(db, seeded_snapshots):
    from edu_cloud.ai.tools.student_diagnosis import get_student_diagnosis

    result = await get_student_diagnosis(
        {"student_id": "nonexistent"},
        _ctx(db, seeded_snapshots.school_id, role="parent"),
    )
    assert result.success
    assert result.data["status"] == "not_found"
