"""F005: Execution-level tests for tools that only had registration metadata tests.

Covers analytics_score (5), analytics_compare (3), grading_ops (3), bank (2), profile (4).
Each tool tested with (input, ctx) → ToolResult pattern.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from types import SimpleNamespace

from edu_cloud.ai.tool_context import ToolContext, ToolResult


def _ctx(db="mock_db", school_id="s1"):
    return ToolContext(db=db, school_id=school_id, user_id="u1", role="admin")


# ── analytics_score ──────────────────────────────────────────────────────

@patch("edu_cloud.modules.analytics.service.exam_summary", new_callable=AsyncMock)
async def test_get_exam_summary_success(mock_svc):
    mock_svc.return_value = {"subjects": [{"code": "SX", "avg": 85.0}]}
    from edu_cloud.ai.tools.analytics_score import get_exam_summary
    result = await get_exam_summary({"exam_id": "e1"}, _ctx())
    assert result.success
    assert result.data["subjects"][0]["avg"] == 85.0


@patch("edu_cloud.modules.analytics.service.exam_summary", new_callable=AsyncMock)
async def test_get_exam_summary_exception(mock_svc):
    mock_svc.side_effect = Exception("DB error")
    from edu_cloud.ai.tools.analytics_score import get_exam_summary
    result = await get_exam_summary({"exam_id": "e1"}, _ctx())
    assert not result.success
    assert "DB error" in result.error


async def test_get_score_distribution_missing_exam_id():
    from edu_cloud.ai.tools.analytics_score import get_score_distribution
    result = await get_score_distribution({}, _ctx())
    assert not result.success
    assert "exam_id" in result.error


async def test_get_question_analysis_exception():
    from edu_cloud.ai.tools.analytics_score import get_question_analysis
    # db=None will cause AttributeError when service tries to use it
    result = await get_question_analysis({"subject_id": "s1"}, _ctx(db=None))
    assert not result.success


@patch("edu_cloud.modules.analytics.service.get_student_exam_scores", new_callable=AsyncMock)
@patch("edu_cloud.modules.student.service.get_student", new_callable=AsyncMock)
async def test_get_student_scores_success(mock_get_student, mock_scores):
    mock_get_student.return_value = SimpleNamespace(name="张三", class_id="c1")
    mock_scores.return_value = [
        {"subject": "SX", "score": 85, "max_score": 100},
        {"subject": "YW", "score": 90, "max_score": 100},
    ]
    from edu_cloud.ai.tools.analytics_score import get_student_scores
    result = await get_student_scores({"exam_id": "e1", "student_id": "stu1"}, _ctx())
    assert result.success
    assert result.data["total_score"] == 175
    assert result.data["student_name"] == "张三"


@patch("edu_cloud.modules.student.service.get_student", new_callable=AsyncMock)
async def test_get_student_scores_not_found(mock_get_student):
    mock_get_student.return_value = None
    from edu_cloud.ai.tools.analytics_score import get_student_scores
    result = await get_student_scores({"exam_id": "e1", "student_id": "x"}, _ctx())
    assert not result.success
    assert "不存在" in result.error


async def test_get_class_scores_missing_exam_id():
    from edu_cloud.ai.tools.analytics_score import get_class_scores
    result = await get_class_scores({"class_id": "c1"}, _ctx())
    assert not result.success
    assert "exam_id" in result.error


async def test_get_class_scores_permission_denied():
    from edu_cloud.ai.tools.analytics_score import get_class_scores
    ctx = ToolContext(db=None, school_id="s1", user_id="u1", role="teacher", class_ids=["c1"])
    result = await get_class_scores({"exam_id": "e1", "class_id": "c99"}, ctx)
    assert not result.success
    assert "无权" in result.error


@patch("edu_cloud.modules.analytics.service.get_effective_scores", new_callable=AsyncMock)
async def test_get_class_scores_success(mock_effective):
    """F005 R3: success path — DB query → subject iteration → aggregation → sorted result."""
    from edu_cloud.ai.tools.analytics_score import get_class_scores

    # Mock students query result (first db.execute call)
    stu_a = SimpleNamespace(id="stu1", name="张三", class_id="c1", school_id="s1")
    stu_b = SimpleNamespace(id="stu2", name="李四", class_id="c1", school_id="s1")
    mock_students_result = MagicMock()
    mock_students_result.scalars.return_value.all.return_value = [stu_a, stu_b]

    # Mock subjects query result (second db.execute call)
    subj_math = SimpleNamespace(id="sub1", exam_id="e1", code="SX", school_id="s1")
    subj_eng = SimpleNamespace(id="sub2", exam_id="e1", code="YY", school_id="s1")
    mock_subjects_result = MagicMock()
    mock_subjects_result.scalars.return_value.all.return_value = [subj_math, subj_eng]

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[mock_students_result, mock_subjects_result])

    # get_effective_scores: math then english
    mock_effective.side_effect = [
        [{"student_id": "stu1", "effective_score": 90}, {"student_id": "stu2", "effective_score": 80}],
        [{"student_id": "stu1", "effective_score": 85}, {"student_id": "stu2", "effective_score": 95}],
    ]

    ctx = ToolContext(db=mock_db, school_id="s1", user_id="u1", role="admin")
    result = await get_class_scores({"exam_id": "e1", "class_id": "c1"}, ctx)

    assert result.success, f"Expected success, got error: {result.error}"
    data = result.data
    assert data["class_id"] == "c1"
    assert len(data["students"]) == 2
    # stu1: 90+85=175, stu2: 80+95=175 — equal totals, verify both present
    totals = {s["student_id"]: s["total_score"] for s in data["students"]}
    assert totals["stu1"] == 175  # 90 + 85
    assert totals["stu2"] == 175  # 80 + 95
    # Verify student names resolved from DB
    names = {s["student_id"]: s["student_name"] for s in data["students"]}
    assert names["stu1"] == "张三"
    assert names["stu2"] == "李四"
    # Verify get_effective_scores called once per subject
    assert mock_effective.call_count == 2


@patch("edu_cloud.modules.analytics.service.get_effective_scores", new_callable=AsyncMock)
async def test_get_class_scores_empty_students(mock_effective):
    """F005 R3: empty class — no students, no scores."""
    from edu_cloud.ai.tools.analytics_score import get_class_scores

    mock_students_result = MagicMock()
    mock_students_result.scalars.return_value.all.return_value = []

    mock_subjects_result = MagicMock()
    mock_subjects_result.scalars.return_value.all.return_value = [
        SimpleNamespace(id="sub1", exam_id="e1", code="SX", school_id="s1"),
    ]

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[mock_students_result, mock_subjects_result])
    mock_effective.return_value = []

    ctx = ToolContext(db=mock_db, school_id="s1", user_id="u1", role="admin")
    result = await get_class_scores({"exam_id": "e1", "class_id": "c1"}, ctx)

    assert result.success
    assert result.data["students"] == []


# ── analytics_compare ────────────────────────────────────────────────────

async def test_compare_classes_missing_exam_id():
    from edu_cloud.ai.tools.analytics_compare import compare_classes
    result = await compare_classes({"class_ids": ["c1"]}, _ctx())
    assert not result.success
    assert "exam_id" in result.error


async def test_rank_students_missing_exam_id():
    from edu_cloud.ai.tools.analytics_compare import rank_students
    result = await rank_students({}, _ctx())
    assert not result.success
    assert "exam_id" in result.error


async def test_get_grade_aggregates_missing_exam_id():
    from edu_cloud.ai.tools.analytics_compare import get_grade_aggregates
    result = await get_grade_aggregates({}, _ctx())
    assert not result.success
    assert "exam_id" in result.error


# ── grading_ops ──────────────────────────────────────────────────────────

@patch("edu_cloud.modules.grading.assignment_service.GradingAssignmentService.get_progress", new_callable=AsyncMock)
async def test_get_grading_progress_success(mock_svc):
    mock_svc.return_value = {"total": 10, "completed": 5}
    from edu_cloud.ai.tools.grading_ops import get_grading_progress
    result = await get_grading_progress({"exam_id": "e1"}, _ctx())
    assert result.success
    assert result.data["total"] == 10


@patch("edu_cloud.modules.grading.quality_service.QualityCheckService.get_quality_report", new_callable=AsyncMock)
async def test_get_quality_report_success(mock_svc):
    mock_svc.return_value = {"checks": 20, "avg_deviation": 1.5}
    from edu_cloud.ai.tools.grading_ops import get_quality_report
    result = await get_quality_report({"exam_id": "e1"}, _ctx())
    assert result.success
    assert result.data["checks"] == 20


async def test_assign_grading_task_exception():
    from edu_cloud.ai.tools.grading_ops import assign_grading_task
    result = await assign_grading_task(
        {"exam_id": "e1", "subject_id": "s1", "question_ids": "q1,q2", "teacher_ids": "t1"},
        _ctx(db=None),
    )
    assert not result.success


# ── bank ─────────────────────────────────────────────────────────────────

@patch("edu_cloud.modules.bank.service.get_error_book_stats", new_callable=AsyncMock)
@patch("edu_cloud.modules.bank.service.get_student_error_book", new_callable=AsyncMock)
async def test_get_student_error_book_success(mock_errors, mock_stats):
    mock_errors.return_value = []
    mock_stats.return_value = {"total": 0}
    from edu_cloud.ai.tools.bank import get_student_error_book
    result = await get_student_error_book({"student_id": "stu1"}, _ctx())
    assert result.success
    assert result.data["errors"] == []


async def test_get_question_stats_exception():
    from edu_cloud.ai.tools.bank import get_question_stats
    result = await get_question_stats({"bank_question_id": "bq1"}, _ctx(db=None))
    assert not result.success


# ── profile ──────────────────────────────────────────────────────────────

@patch("edu_cloud.modules.profile.service.get_student_trend", new_callable=AsyncMock)
async def test_get_student_trend_success(mock_svc):
    mock_svc.return_value = [
        SimpleNamespace(exam_id="e1", subject_code="SX", total_score=85,
                       max_score=100, score_rate=0.85, grade_rank=5, grade_size=50),
    ]
    from edu_cloud.ai.tools.profile import get_student_trend
    result = await get_student_trend({"student_id": "stu1"}, _ctx())
    assert result.success
    assert len(result.data["trend"]) == 1
    assert result.data["trend"][0]["total_score"] == 85


@patch("edu_cloud.modules.profile.service.get_student_knowledge_map", new_callable=AsyncMock)
async def test_get_student_knowledge_map_success(mock_svc):
    mock_svc.return_value = [
        SimpleNamespace(concept_id="kp1", mastery_level=0.7,
                       trend="up", attempt_count=3, recent_scores=[80, 85, 90]),
    ]
    from edu_cloud.ai.tools.profile import get_student_knowledge_map
    result = await get_student_knowledge_map({"student_id": "stu1"}, _ctx())
    assert result.success
    assert result.data["knowledge_map"][0]["mastery_level"] == 0.7


async def test_get_class_knowledge_weakness_permission_denied():
    from edu_cloud.ai.tools.profile import get_class_knowledge_weakness
    ctx = ToolContext(db=None, school_id="s1", user_id="u1", role="teacher", class_ids=["c1"])
    result = await get_class_knowledge_weakness({"class_id": "c99"}, ctx)
    assert not result.success
    assert "无权" in result.error


@patch("edu_cloud.modules.profile.service.get_student_error_pattern", new_callable=AsyncMock)
async def test_get_student_error_pattern_success(mock_svc):
    mock_svc.return_value = [
        SimpleNamespace(subject_code="SX", error_distribution={"concept": 3},
                       total_errors=5, exam_count=2, careless_rate=0.2),
    ]
    from edu_cloud.ai.tools.profile import get_student_error_pattern
    result = await get_student_error_pattern({"student_id": "stu1"}, _ctx())
    assert result.success
    assert result.data["error_patterns"][0]["total_errors"] == 5
