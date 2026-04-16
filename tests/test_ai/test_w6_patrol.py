"""W6 patrol workflow — grading overdue, low submission, score anomalies, dedup dispatch."""
import random
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, func

from edu_cloud.ai.workflow.engine import WorkflowContext
from edu_cloud.models.agent_finding import AgentFinding
from edu_cloud.models.agent_snapshot import ClassExamReport
from edu_cloud.models.school import School
from edu_cloud.modules.exam.models import Exam, ExamResult
from edu_cloud.modules.grading.models import GradingTask
from edu_cloud.modules.homework.models import HomeworkTask, HomeworkSubmission
from edu_cloud.modules.student.models import Class, Student


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ctx(db, school_id: str, trigger_ref: str = "patrol") -> WorkflowContext:
    return WorkflowContext(
        db=db,
        school_id=school_id,
        trigger_ref=trigger_ref,
        run_id="test-run",
        step_outputs={},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def overdue_grading_fixture(db):
    """School + GradingTask pending and created >72h ago."""
    school = School(name="W6巡检校", code="W6PAT", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    old_time = datetime.now(timezone.utc) - timedelta(hours=80)
    task_old = GradingTask(
        subject_id="subj-1",
        status="pending",
        total=10,
        completed=0,
        failed=0,
        created_by="user-1",
        school_id=school.id,
    )
    db.add(task_old)
    await db.flush()
    # Manually set created_at to simulate old record
    task_old.created_at = old_time

    task_fresh = GradingTask(
        subject_id="subj-2",
        status="pending",
        total=5,
        completed=0,
        failed=0,
        created_by="user-1",
        school_id=school.id,
    )
    db.add(task_fresh)
    await db.flush()

    await db.commit()
    return {"school_id": school.id, "overdue_task_id": task_old.id, "fresh_task_id": task_fresh.id}


@pytest.fixture
async def low_submission_fixture(db):
    """School + active HomeworkTask with deadline in 12h and only 1 of 4 students submitted."""
    school = School(name="W6作业校", code="W6HW", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    cls = Class(name="八年级1班", grade="八年级", grade_number=8, school_id=school.id)
    db.add(cls)
    await db.flush()

    students = []
    for i in range(4):
        s = Student(
            name=f"学生{i}",
            student_number=f"W6S{i:03d}",
            school_id=school.id,
            class_id=cls.id,
            grade="八年级",
        )
        db.add(s)
        students.append(s)
    await db.flush()

    deadline = datetime.now(timezone.utc) + timedelta(hours=12)
    task = HomeworkTask(
        school_id=school.id,
        title="数学练习",
        task_type="regular",
        subject_code="SX",
        class_id=cls.id,
        assigned_by="user-1",
        deadline=deadline,
        status="active",
    )
    db.add(task)
    await db.flush()

    # Create 4 submissions, only 1 submitted
    for i, s in enumerate(students):
        sub = HomeworkSubmission(
            task_id=task.id,
            student_id=s.id,
            status="submitted" if i == 0 else "pending",
        )
        db.add(sub)
    await db.flush()

    await db.commit()
    return {
        "school_id": school.id,
        "task_id": task.id,
        "class_id": cls.id,
        "student_count": 4,
    }


@pytest.fixture
async def anomaly_fixture(db):
    """School + 3 classes with ClassExamReport, one outlier."""
    school = School(name="W6异常校", code="W6ANO", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    exam = Exam(
        name="期末考试",
        school_id=school.id,
        status="completed",
        max_score=100,
    )
    db.add(exam)
    await db.flush()

    # Published recently
    exam.updated_at = datetime.now(timezone.utc) - timedelta(hours=2)

    now = datetime.now(timezone.utc)
    # class A: avg=85, class B: avg=82, class C: avg=40 (outlier)
    for cid, avg in [("cls-a", 85.0), ("cls-b", 82.0), ("cls-c", 40.0)]:
        report = ClassExamReport(
            exam_id=exam.id,
            school_id=school.id,
            class_id=cid,
            grade_rank=1,
            class_avg=avg,
            grade_avg=69.0,
            metrics={"student_count": 10},
            version=1,
            status="active",
            computed_at=now,
        )
        db.add(report)

    await db.flush()
    await db.commit()
    return {"school_id": school.id, "exam_id": exam.id}


# ---------------------------------------------------------------------------
# Tests: scan_grading_overdue
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_grading_overdue_detects_old(db, overdue_grading_fixture):
    from edu_cloud.ai.workflow.w6_patrol import scan_grading_overdue

    ctx = _make_ctx(db, overdue_grading_fixture["school_id"])
    result = await scan_grading_overdue(ctx)

    assert result["finding_count"] == 1

    findings = (await db.execute(
        select(AgentFinding).where(
            AgentFinding.finding_type == "grading_overdue",
            AgentFinding.school_id == overdue_grading_fixture["school_id"],
        )
    )).scalars().all()
    assert len(findings) == 1
    assert findings[0].severity == "warning"
    assert findings[0].target_id == overdue_grading_fixture["overdue_task_id"]


@pytest.mark.asyncio
async def test_scan_grading_no_overdue(db):
    """Fresh grading tasks should not produce findings."""
    from edu_cloud.ai.workflow.w6_patrol import scan_grading_overdue

    school = School(name="W6新鲜校", code="W6FR", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    task = GradingTask(
        subject_id="subj-1",
        status="pending",
        total=10,
        completed=0,
        failed=0,
        created_by="user-1",
        school_id=school.id,
    )
    db.add(task)
    await db.flush()
    await db.commit()

    ctx = _make_ctx(db, school.id)
    result = await scan_grading_overdue(ctx)
    assert result["finding_count"] == 0


@pytest.mark.asyncio
async def test_scan_grading_completed_ignored(db):
    """Completed grading tasks should not be flagged even if old."""
    from edu_cloud.ai.workflow.w6_patrol import scan_grading_overdue

    school = School(name="W6完成校", code="W6DONE", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    task = GradingTask(
        subject_id="subj-1",
        status="completed",
        total=10,
        completed=10,
        failed=0,
        created_by="user-1",
        school_id=school.id,
    )
    db.add(task)
    await db.flush()
    task.created_at = datetime.now(timezone.utc) - timedelta(hours=100)
    await db.commit()

    ctx = _make_ctx(db, school.id)
    result = await scan_grading_overdue(ctx)
    assert result["finding_count"] == 0


# ---------------------------------------------------------------------------
# Tests: scan_submission_low
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_submission_low_detects(db, low_submission_fixture):
    from edu_cloud.ai.workflow.w6_patrol import scan_submission_low

    ctx = _make_ctx(db, low_submission_fixture["school_id"])
    result = await scan_submission_low(ctx)

    assert result["finding_count"] == 1

    findings = (await db.execute(
        select(AgentFinding).where(
            AgentFinding.finding_type == "low_submission",
            AgentFinding.school_id == low_submission_fixture["school_id"],
        )
    )).scalars().all()
    assert len(findings) == 1
    assert findings[0].severity == "warning"


@pytest.mark.asyncio
async def test_scan_submission_low_no_issue(db):
    """All submitted -> no finding."""
    from edu_cloud.ai.workflow.w6_patrol import scan_submission_low

    school = School(name="W6全交校", code="W6ALL", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    cls = Class(name="九年级1班", grade="九年级", grade_number=9, school_id=school.id)
    db.add(cls)
    await db.flush()

    students = []
    for i in range(4):
        s = Student(
            name=f"S{i}", student_number=f"W6A{i:03d}",
            school_id=school.id, class_id=cls.id, grade="九年级",
        )
        db.add(s)
        students.append(s)
    await db.flush()

    deadline = datetime.now(timezone.utc) + timedelta(hours=10)
    task = HomeworkTask(
        school_id=school.id, title="英语练习", task_type="regular",
        subject_code="YY", class_id=cls.id, assigned_by="user-1",
        deadline=deadline, status="active",
    )
    db.add(task)
    await db.flush()

    # All submitted
    for s in students:
        sub = HomeworkSubmission(task_id=task.id, student_id=s.id, status="submitted")
        db.add(sub)
    await db.flush()
    await db.commit()

    ctx = _make_ctx(db, school.id)
    result = await scan_submission_low(ctx)
    assert result["finding_count"] == 0


# ---------------------------------------------------------------------------
# Tests: scan_score_anomalies
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_score_anomalies_detects(db, anomaly_fixture):
    from edu_cloud.ai.workflow.w6_patrol import scan_score_anomalies

    ctx = _make_ctx(db, anomaly_fixture["school_id"])
    result = await scan_score_anomalies(ctx)

    # cls-c (avg=40) is a clear outlier from 85/82/40
    assert result["finding_count"] >= 1


# ---------------------------------------------------------------------------
# Tests: deduplicate_and_dispatch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deduplicate_limits_per_role(db):
    """With >10 findings, only 10 per role are notified."""
    from edu_cloud.ai.workflow.w6_patrol import deduplicate_and_dispatch

    school = School(name="W6限流校", code="W6LIM", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    # Create 15 new findings
    for i in range(15):
        f = AgentFinding(
            school_id=school.id,
            finding_type="grading_overdue",
            severity="warning",
            target_type="grading_task",
            target_id=f"task-{i}",
            summary=f"阅卷超时 {i}",
            status="new",
            notify_roles=["academic_director"],
            idempotency_key=f"test:dedup:{i}",
        )
        db.add(f)
    await db.flush()
    await db.commit()

    ctx = _make_ctx(db, school.id)
    result = await deduplicate_and_dispatch(ctx)

    assert result["notified_count"] == 10

    # Verify: 10 notified, 5 remain new
    notified_count = (await db.execute(
        select(func.count()).select_from(AgentFinding).where(
            AgentFinding.school_id == school.id,
            AgentFinding.status == "notified",
        )
    )).scalar()
    assert notified_count == 10

    remaining = (await db.execute(
        select(func.count()).select_from(AgentFinding).where(
            AgentFinding.school_id == school.id,
            AgentFinding.status == "new",
        )
    )).scalar()
    assert remaining == 5


@pytest.mark.asyncio
async def test_deduplicate_multi_role(db):
    """10 per role means different roles can each get 10."""
    from edu_cloud.ai.workflow.w6_patrol import deduplicate_and_dispatch

    school = School(name="W6多角色校", code="W6MR", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    # 5 for academic_director, 5 for grade_leader
    for i in range(5):
        db.add(AgentFinding(
            school_id=school.id, finding_type="grading_overdue", severity="warning",
            target_type="grading_task", target_id=f"t-ad-{i}",
            summary=f"AD finding {i}", status="new",
            notify_roles=["academic_director"],
            idempotency_key=f"mr:ad:{i}",
        ))
        db.add(AgentFinding(
            school_id=school.id, finding_type="low_submission", severity="warning",
            target_type="homework_task", target_id=f"t-gl-{i}",
            summary=f"GL finding {i}", status="new",
            notify_roles=["grade_leader"],
            idempotency_key=f"mr:gl:{i}",
        ))
    await db.flush()
    await db.commit()

    ctx = _make_ctx(db, school.id)
    result = await deduplicate_and_dispatch(ctx)

    # All 10 should be notified (5 per role, both under limit)
    assert result["notified_count"] == 10


# ---------------------------------------------------------------------------
# Tests: workflow definition
# ---------------------------------------------------------------------------

def test_w6_definition_has_4_steps():
    from edu_cloud.ai.workflow.w6_patrol import W6_PATROL
    assert W6_PATROL.name == "patrol"
    assert len(W6_PATROL.steps) == 4
    step_names = [s.name for s in W6_PATROL.steps]
    assert step_names == [
        "scan_grading_overdue",
        "scan_submission_low",
        "scan_score_anomalies",
        "deduplicate_and_dispatch",
    ]


# ---------------------------------------------------------------------------
# Tests: idempotency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_grading_overdue_processing_status(db):
    """A GradingTask in 'processing' status and >72h old should be detected."""
    from edu_cloud.ai.workflow.w6_patrol import scan_grading_overdue

    school = School(name="W6处理中校", code="W6PROC", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    old_time = datetime.now(timezone.utc) - timedelta(hours=80)
    task = GradingTask(
        subject_id="subj-proc",
        status="processing",
        total=10,
        completed=0,
        failed=0,
        created_by="user-1",
        school_id=school.id,
    )
    db.add(task)
    await db.flush()
    task.created_at = old_time
    await db.commit()

    ctx = _make_ctx(db, school.id)
    result = await scan_grading_overdue(ctx)

    assert result["finding_count"] == 1
    findings = (await db.execute(
        select(AgentFinding).where(
            AgentFinding.finding_type == "grading_overdue",
            AgentFinding.school_id == school.id,
        )
    )).scalars().all()
    assert len(findings) == 1
    assert findings[0].detail["status"] == "processing"


@pytest.mark.asyncio
async def test_deduplicate_daily_total_includes_already_notified(db):
    """Pre-existing notified findings today count toward the 10/role/day limit."""
    from edu_cloud.ai.workflow.w6_patrol import deduplicate_and_dispatch

    school = School(name="W6日限校", code="W6DAY", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    # Pre-create 10 already-notified findings for today
    for i in range(10):
        f = AgentFinding(
            school_id=school.id,
            finding_type="grading_overdue",
            severity="warning",
            target_type="grading_task",
            target_id=f"old-task-{i}",
            summary=f"已通知 {i}",
            status="notified",
            notify_roles=["academic_director"],
            idempotency_key=f"day:old:{i}",
        )
        db.add(f)
    await db.flush()

    # Add 1 new finding — should NOT be notified because role already at 10
    new_f = AgentFinding(
        school_id=school.id,
        finding_type="grading_overdue",
        severity="warning",
        target_type="grading_task",
        target_id="new-task-0",
        summary="新发现",
        status="new",
        notify_roles=["academic_director"],
        idempotency_key="day:new:0",
    )
    db.add(new_f)
    await db.flush()
    await db.commit()

    ctx = _make_ctx(db, school.id)
    result = await deduplicate_and_dispatch(ctx)

    assert result["notified_count"] == 0

    # The new finding should remain in 'new' status
    remaining = (await db.execute(
        select(AgentFinding).where(
            AgentFinding.school_id == school.id,
            AgentFinding.status == "new",
        )
    )).scalars().all()
    assert len(remaining) == 1


@pytest.mark.asyncio
async def test_scan_grading_overdue_idempotent(db, overdue_grading_fixture):
    """Running twice should not create duplicate findings."""
    from edu_cloud.ai.workflow.w6_patrol import scan_grading_overdue

    ctx = _make_ctx(db, overdue_grading_fixture["school_id"])
    r1 = await scan_grading_overdue(ctx)
    assert r1["finding_count"] == 1

    await db.commit()

    ctx2 = _make_ctx(db, overdue_grading_fixture["school_id"])
    r2 = await scan_grading_overdue(ctx2)
    assert r2["finding_count"] == 0
