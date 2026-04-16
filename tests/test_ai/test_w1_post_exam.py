"""W1 post-exam analysis steps 1-3 tests."""
import random

import pytest
from sqlalchemy import select

from edu_cloud.ai.workflow.engine import WorkflowContext
from edu_cloud.models.agent_finding import AgentFinding
from edu_cloud.models.agent_snapshot import ExamAnalysisSnapshot, ClassExamReport
from edu_cloud.models.school import School
from edu_cloud.modules.exam.models import Exam, ExamResult, Subject
from edu_cloud.modules.profile.models import StudentExamSnapshot
from edu_cloud.modules.student.models import Class, Student


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def seeded_exam(db):
    """Seed school + 2 classes + students + exam + subjects + results."""
    school = School(name="W1测试校", code="W1TEST", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    cls_a = Class(name="七年级1班", grade="七年级", grade_number=7, school_id=school.id)
    cls_b = Class(name="七年级2班", grade="七年级", grade_number=7, school_id=school.id)
    db.add_all([cls_a, cls_b])
    await db.flush()

    rng = random.Random(42)
    students = []
    for i in range(6):
        cid = cls_a.id if i < 3 else cls_b.id
        s = Student(
            name=f"学生{i}",
            student_number=f"W{i:03d}",
            school_id=school.id,
            class_id=cid,
            grade="七年级",
        )
        db.add(s)
        students.append(s)
    await db.flush()

    exam = Exam(
        name="期中数学",
        subject_code="SX",
        subject_name="数学",
        max_score=150,
        school_id=school.id,
        semester="2025-2026-2",
    )
    db.add(exam)
    await db.flush()

    subj_sx = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    subj_yw = Subject(exam_id=exam.id, name="语文", code="YW", school_id=school.id)
    db.add_all([subj_sx, subj_yw])
    await db.flush()

    for s in students:
        score = round(rng.gauss(100, 15), 1)
        score = max(0, min(150, score))
        db.add(ExamResult(
            exam_id=exam.id,
            student_id=s.id,
            school_id=school.id,
            total_score=score,
            detail_scores={"SX": score * 0.6, "YW": score * 0.4},
        ))
    await db.commit()

    return {
        "school_id": school.id,
        "exam_id": exam.id,
        "class_ids": [cls_a.id, cls_b.id],
        "student_ids": [s.id for s in students],
        "semester": "2025-2026-2",
    }


@pytest.fixture
async def seeded_exam_with_outlier(db):
    """Seed with 3 classes; one class has much lower scores (for anomaly detection)."""
    school = School(name="W1异常校", code="W1OUT", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    cls_a = Class(name="七年级1班", grade="七年级", grade_number=7, school_id=school.id)
    cls_b = Class(name="七年级2班", grade="七年级", grade_number=7, school_id=school.id)
    cls_c = Class(name="七年级3班", grade="七年级", grade_number=7, school_id=school.id)
    db.add_all([cls_a, cls_b, cls_c])
    await db.flush()

    rng = random.Random(99)
    students = []
    class_ids = [cls_a.id, cls_b.id, cls_c.id]
    for ci, cid in enumerate(class_ids):
        for j in range(5):
            s = Student(
                name=f"学生{ci}_{j}",
                student_number=f"O{ci}{j:02d}",
                school_id=school.id,
                class_id=cid,
                grade="七年级",
            )
            db.add(s)
            students.append(s)
    await db.flush()

    exam = Exam(
        name="期末综合",
        subject_code="ZH",
        subject_name="综合",
        max_score=100,
        school_id=school.id,
        semester="2025-2026-2",
    )
    db.add(exam)
    await db.flush()

    subj = Subject(exam_id=exam.id, name="综合", code="ZH", school_id=school.id)
    db.add(subj)
    await db.flush()

    for s in students:
        # cls_c (index 10-14) gets much lower scores
        idx = students.index(s)
        if idx >= 10:
            score = round(rng.gauss(40, 8), 1)
        else:
            score = round(rng.gauss(80, 10), 1)
        score = max(0, min(100, score))
        db.add(ExamResult(
            exam_id=exam.id,
            student_id=s.id,
            school_id=school.id,
            total_score=score,
            detail_scores={"ZH": score},
        ))
    await db.commit()

    return {
        "school_id": school.id,
        "exam_id": exam.id,
        "class_ids": [cls_a.id, cls_b.id, cls_c.id],
        "outlier_class_id": cls_c.id,
        "student_ids": [s.id for s in students],
        "semester": "2025-2026-2",
    }


def _make_ctx(db, school_id: str, exam_id: str, step_outputs: dict | None = None):
    return WorkflowContext(
        db=db,
        school_id=school_id,
        trigger_ref=exam_id,
        run_id="test-run-001",
        step_outputs=step_outputs or {},
    )


# ---------------------------------------------------------------------------
# Step 1: compute_exam_snapshot
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compute_exam_snapshot_creates_overview(db, seeded_exam):
    from edu_cloud.ai.workflow.w1_post_exam import compute_exam_snapshot

    ctx = _make_ctx(db, seeded_exam["school_id"], seeded_exam["exam_id"])
    result = await compute_exam_snapshot(ctx)

    assert "snapshot_count" in result
    assert result["snapshot_count"] >= 1

    # Verify school_overview snapshot exists
    rows = (await db.execute(
        select(ExamAnalysisSnapshot).where(
            ExamAnalysisSnapshot.exam_id == seeded_exam["exam_id"],
            ExamAnalysisSnapshot.snapshot_type == "school_overview",
        )
    )).scalars().all()
    assert len(rows) == 1
    metrics = rows[0].metrics
    assert "avg" in metrics
    assert "total_students" in metrics
    assert metrics["total_students"] == 6


@pytest.mark.asyncio
async def test_compute_exam_snapshot_creates_subject_details(db, seeded_exam):
    from edu_cloud.ai.workflow.w1_post_exam import compute_exam_snapshot

    ctx = _make_ctx(db, seeded_exam["school_id"], seeded_exam["exam_id"])
    await compute_exam_snapshot(ctx)

    # Should have subject_detail snapshots for SX and YW
    rows = (await db.execute(
        select(ExamAnalysisSnapshot).where(
            ExamAnalysisSnapshot.exam_id == seeded_exam["exam_id"],
            ExamAnalysisSnapshot.snapshot_type == "subject_detail",
        )
    )).scalars().all()
    assert len(rows) == 2
    codes = {r.subject_code for r in rows}
    assert codes == {"SX", "YW"}
    for r in rows:
        assert "avg" in r.metrics
        assert "pass_rate" in r.metrics


# ---------------------------------------------------------------------------
# Step 2: compute_class_reports
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compute_class_reports_per_class(db, seeded_exam):
    from edu_cloud.ai.workflow.w1_post_exam import (
        compute_exam_snapshot,
        compute_class_reports,
    )

    ctx = _make_ctx(db, seeded_exam["school_id"], seeded_exam["exam_id"])
    snap_out = await compute_exam_snapshot(ctx)

    ctx2 = _make_ctx(
        db, seeded_exam["school_id"], seeded_exam["exam_id"],
        step_outputs={"compute_exam_snapshot": snap_out},
    )
    result = await compute_class_reports(ctx2)

    assert result["report_count"] == 2
    assert "grade_avg" in result

    rows = (await db.execute(
        select(ClassExamReport).where(
            ClassExamReport.exam_id == seeded_exam["exam_id"],
        )
    )).scalars().all()
    assert len(rows) == 2

    # grade_rank should be 1 and 2
    ranks = sorted(r.grade_rank for r in rows)
    assert ranks == [1, 2]

    # All reports should have class_avg and grade_avg
    for r in rows:
        assert r.class_avg is not None
        assert r.grade_avg is not None


# ---------------------------------------------------------------------------
# Step 3: compute_student_diagnoses
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compute_student_diagnoses_creates_snapshots(db, seeded_exam):
    from edu_cloud.ai.workflow.w1_post_exam import (
        compute_exam_snapshot,
        compute_class_reports,
        compute_student_diagnoses,
    )

    ctx = _make_ctx(db, seeded_exam["school_id"], seeded_exam["exam_id"])
    snap_out = await compute_exam_snapshot(ctx)

    ctx2 = _make_ctx(
        db, seeded_exam["school_id"], seeded_exam["exam_id"],
        step_outputs={"compute_exam_snapshot": snap_out},
    )
    class_out = await compute_class_reports(ctx2)

    ctx3 = _make_ctx(
        db, seeded_exam["school_id"], seeded_exam["exam_id"],
        step_outputs={
            "compute_exam_snapshot": snap_out,
            "compute_class_reports": class_out,
        },
    )
    result = await compute_student_diagnoses(ctx3)

    assert result["student_count"] == 6

    rows = (await db.execute(
        select(StudentExamSnapshot).where(
            StudentExamSnapshot.exam_id == seeded_exam["exam_id"],
        )
    )).scalars().all()
    assert len(rows) == 6

    for r in rows:
        assert r.total_score >= 0
        assert r.max_score == 150
        assert 0 <= r.score_rate <= 1.0
        assert r.school_id == seeded_exam["school_id"]


@pytest.mark.asyncio
async def test_compute_student_diagnoses_populates_ranks(db, seeded_exam):
    """F03: class_rank, grade_rank, class_size, grade_size must be populated."""
    from edu_cloud.ai.workflow.w1_post_exam import (
        compute_exam_snapshot,
        compute_class_reports,
        compute_student_diagnoses,
    )

    ctx = _make_ctx(db, seeded_exam["school_id"], seeded_exam["exam_id"])
    await compute_exam_snapshot(ctx)
    ctx2 = _make_ctx(db, seeded_exam["school_id"], seeded_exam["exam_id"])
    await compute_class_reports(ctx2)
    ctx3 = _make_ctx(db, seeded_exam["school_id"], seeded_exam["exam_id"])
    await compute_student_diagnoses(ctx3)

    rows = (await db.execute(
        select(StudentExamSnapshot).where(
            StudentExamSnapshot.exam_id == seeded_exam["exam_id"],
        )
    )).scalars().all()
    assert len(rows) == 6

    for r in rows:
        assert r.class_rank is not None, f"class_rank None for student {r.student_id}"
        assert r.grade_rank is not None, f"grade_rank None for student {r.student_id}"
        assert r.class_size is not None, f"class_size None for student {r.student_id}"
        assert r.grade_size is not None, f"grade_size None for student {r.student_id}"
        assert 1 <= r.class_rank <= r.class_size
        assert 1 <= r.grade_rank <= r.grade_size
        assert r.grade_size == 6  # total students


@pytest.mark.asyncio
async def test_compute_student_diagnoses_sets_class_id(db, seeded_exam):
    """StudentExamSnapshot should record class_id_at_exam."""
    from edu_cloud.ai.workflow.w1_post_exam import (
        compute_exam_snapshot,
        compute_class_reports,
        compute_student_diagnoses,
    )

    ctx = _make_ctx(db, seeded_exam["school_id"], seeded_exam["exam_id"])
    await compute_exam_snapshot(ctx)
    ctx2 = _make_ctx(db, seeded_exam["school_id"], seeded_exam["exam_id"])
    await compute_class_reports(ctx2)
    ctx3 = _make_ctx(db, seeded_exam["school_id"], seeded_exam["exam_id"])
    await compute_student_diagnoses(ctx3)

    rows = (await db.execute(
        select(StudentExamSnapshot).where(
            StudentExamSnapshot.exam_id == seeded_exam["exam_id"],
        )
    )).scalars().all()
    class_ids_in_snapshot = {r.class_id_at_exam for r in rows}
    assert class_ids_in_snapshot == set(seeded_exam["class_ids"])


# ---------------------------------------------------------------------------
# Outlier fixture smoke test (for Task 8)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_outlier_fixture_has_low_scores(db, seeded_exam_with_outlier):
    """The outlier class should have significantly lower average score."""
    from edu_cloud.ai.workflow.w1_post_exam import (
        compute_exam_snapshot,
        compute_class_reports,
    )

    data = seeded_exam_with_outlier
    ctx = _make_ctx(db, data["school_id"], data["exam_id"])
    await compute_exam_snapshot(ctx)
    ctx2 = _make_ctx(db, data["school_id"], data["exam_id"])
    result = await compute_class_reports(ctx2)

    assert result["report_count"] == 3

    rows = (await db.execute(
        select(ClassExamReport).where(
            ClassExamReport.exam_id == data["exam_id"],
        )
    )).scalars().all()

    outlier_report = [r for r in rows if r.class_id == data["outlier_class_id"]][0]
    other_reports = [r for r in rows if r.class_id != data["outlier_class_id"]]

    # Outlier class avg should be well below grade avg
    assert outlier_report.class_avg < outlier_report.grade_avg
    # And below all other class averages
    for other in other_reports:
        assert outlier_report.class_avg < other.class_avg


# ---------------------------------------------------------------------------
# Step 4: detect_anomalies
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_detect_anomalies_finds_outlier_class(db, seeded_exam_with_outlier):
    """班级均分偏离年级 >2σ → critical finding."""
    from edu_cloud.ai.workflow.w1_post_exam import (
        compute_exam_snapshot, compute_class_reports, detect_anomalies
    )
    from edu_cloud.models.agent_finding import AgentFinding

    data = seeded_exam_with_outlier
    ctx = _make_ctx(db, data["school_id"], data["exam_id"])
    await compute_exam_snapshot(ctx)
    ctx.step_outputs["compute_class_reports"] = await compute_class_reports(ctx)
    result = await detect_anomalies(ctx)
    assert result["finding_count"] >= 1

    findings = (await db.execute(
        select(AgentFinding).where(AgentFinding.school_id == data["school_id"])
    )).scalars().all()
    assert any(f.severity == "critical" for f in findings)


@pytest.mark.asyncio
async def test_detect_anomalies_idempotent(db, seeded_exam_with_outlier):
    """Same anomaly not created twice."""
    from edu_cloud.ai.workflow.w1_post_exam import (
        compute_exam_snapshot, compute_class_reports, detect_anomalies
    )

    data = seeded_exam_with_outlier
    ctx = _make_ctx(db, data["school_id"], data["exam_id"])
    await compute_exam_snapshot(ctx)
    ctx.step_outputs["compute_class_reports"] = await compute_class_reports(ctx)
    r1 = await detect_anomalies(ctx)
    r2 = await detect_anomalies(ctx)
    assert r2["finding_count"] == 0  # second run skipped by idempotency


# ---------------------------------------------------------------------------
# Step 5: dispatch_notifications
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_notifications_marks_notified(db, seeded_exam_with_outlier):
    """New findings get status set to 'notified'."""
    from edu_cloud.ai.workflow.w1_post_exam import (
        compute_exam_snapshot, compute_class_reports, detect_anomalies,
        dispatch_notifications,
    )
    from edu_cloud.models.agent_finding import AgentFinding

    data = seeded_exam_with_outlier
    ctx = _make_ctx(db, data["school_id"], data["exam_id"])
    await compute_exam_snapshot(ctx)
    ctx.step_outputs["compute_class_reports"] = await compute_class_reports(ctx)
    ctx.step_outputs["detect_anomalies"] = await detect_anomalies(ctx)
    result = await dispatch_notifications(ctx)
    assert result["notified_count"] >= 1

    findings = (await db.execute(
        select(AgentFinding).where(AgentFinding.school_id == data["school_id"])
    )).scalars().all()
    assert all(f.status == "notified" for f in findings)


# ---------------------------------------------------------------------------
# F05: empty exam data
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compute_exam_snapshot_empty_returns_zero(db):
    """F05: Exam with no results returns snapshot_count=0 instead of ValueError."""
    from edu_cloud.ai.workflow.w1_post_exam import compute_exam_snapshot

    school = School(name="空考试校", code="EMPTY01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    exam = Exam(
        name="空考试", subject_code="SX", subject_name="数学",
        max_score=100, school_id=school.id, semester="2025-2026-2",
    )
    db.add(exam)
    await db.commit()

    ctx = _make_ctx(db, school.id, exam.id)
    result = await compute_exam_snapshot(ctx)
    assert result == {"snapshot_count": 0}


# ---------------------------------------------------------------------------
# F02: producer→consumer integration (snapshot type + status alignment)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_producer_consumer_status_alignment(db, seeded_exam):
    """F02: W1 produces status='ready' + type='subject_detail' that get_exam_overview reads."""
    from edu_cloud.ai.workflow.w1_post_exam import compute_exam_snapshot

    ctx = _make_ctx(db, seeded_exam["school_id"], seeded_exam["exam_id"])
    await compute_exam_snapshot(ctx)

    # Verify all snapshots use status='ready'
    all_snaps = (await db.execute(
        select(ExamAnalysisSnapshot).where(
            ExamAnalysisSnapshot.exam_id == seeded_exam["exam_id"],
        )
    )).scalars().all()
    for snap in all_snaps:
        assert snap.status == "ready", f"Expected status='ready', got '{snap.status}'"

    # Verify subject snapshots use type='subject_detail'
    subject_snaps = [s for s in all_snaps if s.snapshot_type != "school_overview"]
    for snap in subject_snaps:
        assert snap.snapshot_type == "subject_detail", f"Expected 'subject_detail', got '{snap.snapshot_type}'"

    # Now verify get_exam_overview can actually read these
    from edu_cloud.ai.tools.exam_overview import get_exam_overview
    from edu_cloud.ai.tool_context import ToolContext

    tool_ctx = ToolContext(
        db=db, school_id=seeded_exam["school_id"],
        user_id="u1", role="principal",
    )
    result = await get_exam_overview({"exam_id": seeded_exam["exam_id"]}, tool_ctx)
    assert result.success
    assert result.data["status"] == "ready"
    assert len(result.data["subject_breakdowns"]) == 2  # SX + YW


# ---------------------------------------------------------------------------
# F06: cross-run isolation — dispatch only this run's findings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_notifications_scoped_to_run(db, seeded_exam_with_outlier):
    """F06: dispatch_notifications only marks findings from this workflow run."""
    from edu_cloud.ai.workflow.w1_post_exam import (
        compute_exam_snapshot, compute_class_reports, detect_anomalies,
        dispatch_notifications,
    )
    from edu_cloud.models.agent_finding import AgentFinding

    data = seeded_exam_with_outlier

    # Pre-existing "new" finding from a different source
    pre_existing = AgentFinding(
        school_id=data["school_id"],
        finding_type="other_type",
        severity="warning",
        target_type="student",
        target_id="stu-999",
        summary="Pre-existing finding",
        status="new",
        notify_roles=["academic_director"],
        idempotency_key="pre-existing-key-001",
    )
    db.add(pre_existing)
    await db.flush()

    ctx = _make_ctx(db, data["school_id"], data["exam_id"])
    await compute_exam_snapshot(ctx)
    ctx.step_outputs["compute_class_reports"] = await compute_class_reports(ctx)
    ctx.step_outputs["detect_anomalies"] = await detect_anomalies(ctx)
    await dispatch_notifications(ctx)

    # Pre-existing finding should still be "new" (not touched by dispatch)
    await db.refresh(pre_existing)
    assert pre_existing.status == "new", "dispatch_notifications should not touch findings from other runs"
