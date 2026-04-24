"""Integration tests for grading quality router and service."""
import pytest

from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.grading.models import GradingQualityCheck
from edu_cloud.modules.grading.quality_service import QualityCheckService
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def quality_setup(db):
    """Seed school + user + exam + subject + question for quality tests."""
    school = School(name="质检测试校", code="QC01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    user = User(username="qc_admin", display_name="质检管理员")
    user.set_password("123456")
    db.add(user)
    await db.flush()

    role = UserRole(
        user_id=user.id, role="academic_director",
        school_id=school.id, is_primary=True,
    )
    db.add(role)
    await db.flush()

    exam = Exam(name="期中联考", school_id=school.id)
    db.add(exam)
    await db.flush()

    subject = Subject(
        exam_id=exam.id, name="数学", code="SX", school_id=school.id,
    )
    db.add(subject)
    await db.flush()

    question = Question(
        subject_id=subject.id, name="第1题",
        question_type="essay", max_score=10.0, school_id=school.id,
    )
    db.add(question)
    await db.flush()

    await db.commit()

    token = create_access_token({
        "sub": user.id, "school_id": school.id, "role": "academic_director",
    })
    headers = {"Authorization": f"Bearer {token}"}

    return {
        "school": school,
        "user": user,
        "exam": exam,
        "subject": subject,
        "question": question,
        "headers": headers,
    }


# ── API endpoint tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_quality_report_empty(client, quality_setup):
    """No checks exist -> report returns all zeros."""
    setup = quality_setup
    resp = await client.get(
        f"/api/v1/grading/quality-report/{setup['exam'].id}",
        headers=setup["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_checks"] == 0
    assert data["reviewed"] == 0
    assert data["pending"] == 0
    assert data["avg_deviation"] == 0
    assert data["high_severity_count"] == 0
    assert data["has_blocking_issues"] is False


@pytest.mark.asyncio
async def test_quality_report_with_reviewed_checks(client, db, quality_setup):
    """Create reviewed checks -> correct stats in report."""
    setup = quality_setup

    # Create 3 checks: 2 reviewed, 1 pending
    for i, (status, score, dev, sev) in enumerate([
        ("reviewed", 8.0, 2.0, "low"),
        ("reviewed", 6.0, 4.0, "med"),
        ("pending", None, None, None),
    ]):
        check = GradingQualityCheck(
            exam_id=setup["exam"].id,
            subject_id=setup["subject"].id,
            question_id=setup["question"].id,
            check_type="sampling",
            original_score=10.0,
            check_score=score,
            deviation=dev,
            severity=sev,
            status=status,
            school_id=setup["school"].id,
        )
        db.add(check)
    await db.commit()

    resp = await client.get(
        f"/api/v1/grading/quality-report/{setup['exam'].id}",
        headers=setup["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_checks"] == 3
    assert data["reviewed"] == 2
    assert data["pending"] == 1
    # avg_deviation = (2.0 + 4.0) / 2 = 3.0
    assert data["avg_deviation"] == 3.0
    assert data["high_severity_count"] == 0
    assert data["has_blocking_issues"] is False


@pytest.mark.asyncio
async def test_quality_report_high_severity(client, db, quality_setup):
    """has_blocking_issues=True when a high severity check exists."""
    setup = quality_setup

    check = GradingQualityCheck(
        exam_id=setup["exam"].id,
        subject_id=setup["subject"].id,
        question_id=setup["question"].id,
        check_type="sampling",
        original_score=10.0,
        check_score=3.0,
        deviation=7.0,
        severity="high",
        status="reviewed",
        school_id=setup["school"].id,
    )
    db.add(check)
    await db.commit()

    resp = await client.get(
        f"/api/v1/grading/quality-report/{setup['exam'].id}",
        headers=setup["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["high_severity_count"] == 1
    assert data["has_blocking_issues"] is True


@pytest.mark.asyncio
async def test_quality_report_wrong_school(client, db, quality_setup):
    """Report for wrong school_id returns empty (zero counts)."""
    setup = quality_setup

    # Add a check under the real school
    check = GradingQualityCheck(
        exam_id=setup["exam"].id,
        subject_id=setup["subject"].id,
        question_id=setup["question"].id,
        check_type="sampling",
        original_score=10.0,
        status="reviewed",
        severity="low",
        deviation=1.0,
        check_score=9.0,
        school_id=setup["school"].id,
    )
    db.add(check)
    await db.commit()

    # Create a platform_admin who can pass a different school_id query param
    admin = User(username="plat_admin_qc", display_name="平台管理员")
    admin.set_password("123456")
    db.add(admin)
    await db.flush()
    db.add(UserRole(user_id=admin.id, role="platform_admin", is_primary=True))
    await db.commit()

    token = create_access_token({
        "sub": admin.id, "role": "platform_admin",
    })
    headers = {"Authorization": f"Bearer {token}"}

    # Request with a non-existent school_id
    resp = await client.get(
        f"/api/v1/grading/quality-report/{setup['exam'].id}?school_id=nonexistent-school",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_checks"] == 0
    assert data["reviewed"] == 0


# ── Service-level tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_sampling_checks(db, quality_setup):
    """Service creates correct number of sample checks from source_data."""
    setup = quality_setup

    source_data = [
        {"question_id": setup["question"].id, "score": 8.0, "result_id": f"r{i}", "grader_id": f"g{i}"}
        for i in range(20)
    ]

    checks = await QualityCheckService.create_sampling_checks(
        db,
        exam_id=setup["exam"].id,
        subject_id=setup["subject"].id,
        source_data=source_data,
        rate=0.1,
        school_id=setup["school"].id,
    )

    # 10% of 20 = 2, but max(1, int(20*0.1)) = 2
    assert len(checks) == 2
    for c in checks:
        assert c.exam_id == setup["exam"].id
        assert c.subject_id == setup["subject"].id
        assert c.check_type == "sampling"
        assert c.original_score == 8.0
        assert c.school_id == setup["school"].id
        assert c.status == "pending"


@pytest.mark.asyncio
async def test_review_check_updates_fields(db, quality_setup):
    """review_check sets deviation, severity, status, and related fields."""
    setup = quality_setup

    check = GradingQualityCheck(
        exam_id=setup["exam"].id,
        subject_id=setup["subject"].id,
        question_id=setup["question"].id,
        check_type="sampling",
        original_score=8.0,
        school_id=setup["school"].id,
    )
    db.add(check)
    await db.flush()

    reviewed = await QualityCheckService.review_check(
        db,
        check_id=check.id,
        checker_id=setup["user"].id,
        check_score=7.0,
        max_score=10.0,
        comment="Slightly off",
    )

    assert reviewed.status == "reviewed"
    assert reviewed.check_score == 7.0
    assert reviewed.deviation == 1.0  # abs(7.0 - 8.0)
    assert reviewed.checker_id == setup["user"].id
    assert reviewed.comment == "Slightly off"
    # 1.0 / 10.0 * 100 = 10% -> "low"
    assert reviewed.severity == "low"


@pytest.mark.asyncio
async def test_review_check_severity_levels(db, quality_setup):
    """Severity: low <= 10%, med <= 20%, high > 20%."""
    setup = quality_setup

    async def _make_check(original: float) -> GradingQualityCheck:
        c = GradingQualityCheck(
            exam_id=setup["exam"].id,
            subject_id=setup["subject"].id,
            question_id=setup["question"].id,
            check_type="sampling",
            original_score=original,
            school_id=setup["school"].id,
        )
        db.add(c)
        await db.flush()
        return c

    # low: deviation 0.5 / max 10 = 5%
    c1 = await _make_check(original=5.0)
    r1 = await QualityCheckService.review_check(
        db, check_id=c1.id, checker_id="u1", check_score=5.5, max_score=10.0,
    )
    assert r1.severity == "low"

    # med: deviation 1.5 / max 10 = 15%
    c2 = await _make_check(original=5.0)
    r2 = await QualityCheckService.review_check(
        db, check_id=c2.id, checker_id="u1", check_score=6.5, max_score=10.0,
    )
    assert r2.severity == "med"

    # high: deviation 3.0 / max 10 = 30%
    c3 = await _make_check(original=5.0)
    r3 = await QualityCheckService.review_check(
        db, check_id=c3.id, checker_id="u1", check_score=8.0, max_score=10.0,
    )
    assert r3.severity == "high"
