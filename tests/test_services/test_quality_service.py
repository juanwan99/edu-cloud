import pytest
from edu_cloud.modules.grading.quality_service import QualityCheckService
from edu_cloud.modules.grading.models import GradingQualityCheck


@pytest.mark.asyncio
async def test_create_sampling_checks(db):
    checks = await QualityCheckService.create_sampling_checks(
        db, exam_id="e1", subject_id="s1",
        source_data=[
            {"question_id": "q1", "result_id": "r1", "grader_id": "t1", "score": 8.0},
            {"question_id": "q2", "result_id": "r2", "grader_id": "t1", "score": 6.0},
            {"question_id": "q3", "result_id": "r3", "grader_id": "t2", "score": 9.0},
        ],
        rate=1.0,
        school_id="s1",
    )
    assert len(checks) == 3
    assert all(c.check_type == "sampling" for c in checks)
    assert all(c.status == "pending" for c in checks)


@pytest.mark.asyncio
async def test_create_sampling_rate(db):
    """rate=0.5 大约抽一半"""
    source = [{"question_id": f"q{i}", "result_id": f"r{i}", "grader_id": "t1", "score": 5.0} for i in range(10)]
    checks = await QualityCheckService.create_sampling_checks(
        db, exam_id="e1", subject_id="s1", source_data=source, rate=0.5, school_id="s1",
    )
    assert 3 <= len(checks) <= 7


@pytest.mark.asyncio
async def test_review_check_low_severity(db):
    check = GradingQualityCheck(
        exam_id="e1", subject_id="s1", question_id="q1",
        check_type="sampling", original_score=8.0, school_id="s1",
    )
    db.add(check)
    await db.flush()

    result = await QualityCheckService.review_check(
        db, check_id=check.id, checker_id="reviewer-1",
        check_score=7.5, max_score=10.0,
    )
    assert result.status == "reviewed"
    assert result.deviation == 0.5
    assert result.severity == "low"


@pytest.mark.asyncio
async def test_review_check_high_severity(db):
    check = GradingQualityCheck(
        exam_id="e1", subject_id="s1", question_id="q1",
        check_type="sampling", original_score=8.0, school_id="s1",
    )
    db.add(check)
    await db.flush()

    result = await QualityCheckService.review_check(
        db, check_id=check.id, checker_id="reviewer-1",
        check_score=4.0, max_score=10.0,
    )
    assert result.severity == "high"


@pytest.mark.asyncio
async def test_get_quality_report(db):
    for i, (score, check_score) in enumerate([(8.0, 7.5), (6.0, 3.0)]):
        c = GradingQualityCheck(
            exam_id="e1", subject_id="s1", question_id=f"q{i}",
            check_type="sampling", original_score=score,
            check_score=check_score, deviation=abs(score - check_score),
            severity="low" if abs(score - check_score) <= 1 else "high",
            status="reviewed", school_id="s1",
        )
        db.add(c)
    await db.flush()

    report = await QualityCheckService.get_quality_report(db, "e1", school_id="s1")
    assert report["total_checks"] == 2
    assert report["reviewed"] == 2
    assert report["high_severity_count"] == 1
    assert report["has_blocking_issues"] is True


@pytest.mark.asyncio
async def test_get_quality_report_empty(db):
    report = await QualityCheckService.get_quality_report(db, "nonexistent", school_id="s1")
    assert report["total_checks"] == 0
    assert report["has_blocking_issues"] is False
