"""Agent evolution 数据模型单测 — 8 张新表。"""
import pytest
from sqlalchemy.exc import IntegrityError


# ---------- GuardianStudentLink ----------

@pytest.mark.asyncio
async def test_create_guardian_link(db):
    from edu_cloud.models.guardian import GuardianStudentLink

    link = GuardianStudentLink(
        school_id="school-1",
        guardian_user_id="user-parent-1",
        student_id="STU001",
        relationship="母亲",
        is_primary=True,
    )
    db.add(link)
    await db.flush()
    assert link.id is not None
    assert link.guardian_user_id == "user-parent-1"
    assert link.student_id == "STU001"
    assert link.relationship == "母亲"
    assert link.is_primary is True
    assert link.school_id == "school-1"
    assert link.created_at is not None


@pytest.mark.asyncio
async def test_guardian_link_unique_constraint(db):
    from edu_cloud.models.guardian import GuardianStudentLink

    link1 = GuardianStudentLink(
        school_id="school-1",
        guardian_user_id="user-parent-1",
        student_id="STU001",
        relationship="母亲",
    )
    link2 = GuardianStudentLink(
        school_id="school-1",
        guardian_user_id="user-parent-1",
        student_id="STU001",
        relationship="父亲",
    )
    db.add(link1)
    await db.flush()
    db.add(link2)
    with pytest.raises(IntegrityError):
        await db.flush()


# ---------- WorkflowRun ----------

@pytest.mark.asyncio
async def test_create_workflow_run(db):
    from edu_cloud.models.workflow import WorkflowRun

    run = WorkflowRun(
        school_id="school-1",
        workflow_name="post_exam_analysis",
        trigger_type="event",
        trigger_ref="exam-uuid-1",
        idempotency_key="post_exam_analysis:exam-uuid-1",
        status="running",
    )
    db.add(run)
    await db.flush()
    assert run.id is not None
    assert run.retry_count == 0
    assert run.current_step == 0
    assert run.total_steps == 0
    assert run.next_retry_at is None
    assert run.started_at is not None
    assert run.completed_at is None
    assert run.last_error is None


@pytest.mark.asyncio
async def test_workflow_idempotency_key_unique(db):
    from edu_cloud.models.workflow import WorkflowRun

    run1 = WorkflowRun(
        school_id="school-1",
        workflow_name="w1", trigger_type="event", trigger_ref="ref-1",
        idempotency_key="same-key", status="running",
    )
    run2 = WorkflowRun(
        school_id="school-1",
        workflow_name="w1", trigger_type="event", trigger_ref="ref-2",
        idempotency_key="same-key", status="pending",
    )
    db.add(run1)
    await db.flush()
    db.add(run2)
    with pytest.raises(IntegrityError):
        await db.flush()


# ---------- WorkflowStep ----------

@pytest.mark.asyncio
async def test_create_workflow_step(db):
    from edu_cloud.models.workflow import WorkflowRun, WorkflowStep

    run = WorkflowRun(
        school_id="school-1",
        workflow_name="w1", trigger_type="event", trigger_ref="ref-1",
        idempotency_key="unique-key-step-test", status="running",
    )
    db.add(run)
    await db.flush()

    step = WorkflowStep(
        run_id=run.id,
        step_index=0,
        step_name="collect_scores",
        status="pending",
    )
    db.add(step)
    await db.flush()
    assert step.id is not None
    assert step.run_id == run.id
    assert step.step_index == 0
    assert step.step_name == "collect_scores"
    assert step.status == "pending"
    assert step.started_at is None
    assert step.completed_at is None
    assert step.error is None


# ---------- ExamAnalysisSnapshot ----------

@pytest.mark.asyncio
async def test_create_exam_analysis_snapshot(db):
    from edu_cloud.models.agent_snapshot import ExamAnalysisSnapshot

    snap = ExamAnalysisSnapshot(
        school_id="school-1",
        exam_id="exam-uuid-1",
        snapshot_type="class_summary",
        target_type="class",
        target_id="class-1",
        subject_code="SX",
        semester="2025-2026-2",
        status="ready",
        metrics={"avg": 85.3, "max": 100},
    )
    db.add(snap)
    await db.flush()
    assert snap.id is not None
    assert snap.status == "ready"
    assert snap.version == 1
    assert snap.computed_at is not None
    assert snap.metrics["avg"] == 85.3


# ---------- ClassExamReport ----------

@pytest.mark.asyncio
async def test_create_class_exam_report(db):
    from edu_cloud.models.agent_snapshot import ClassExamReport

    report = ClassExamReport(
        school_id="school-1",
        exam_id="exam-uuid-1",
        class_id="class-7-2",
        grade_rank=3,
        class_avg=88.5,
        grade_avg=85.0,
        vs_last_exam=2.3,
        status="ready",
    )
    db.add(report)
    await db.flush()
    assert report.id is not None
    assert report.grade_rank == 3
    assert report.class_avg == 88.5
    assert report.version == 1
    assert report.computed_at is not None


# ---------- AgentFinding ----------

@pytest.mark.asyncio
async def test_create_agent_finding(db):
    from edu_cloud.models.agent_finding import AgentFinding

    finding = AgentFinding(
        school_id="school-1",
        finding_type="score_anomaly",
        severity="high",
        target_type="student",
        target_id="stu-001",
        summary="数学成绩异常下滑 30 分",
        detail={"prev_score": 120, "curr_score": 90},
        status="open",
        notify_roles=["homeroom_teacher", "parent"],
        idempotency_key="score_anomaly:stu-001:exam-1",
    )
    db.add(finding)
    await db.flush()
    assert finding.id is not None
    assert finding.finding_type == "score_anomaly"
    assert finding.severity == "high"
    assert finding.target_id == "stu-001"
    assert finding.detail["prev_score"] == 120
    assert finding.notify_roles == ["homeroom_teacher", "parent"]
    assert finding.resolved_at is None


@pytest.mark.asyncio
async def test_finding_idempotency_key_unique(db):
    from edu_cloud.models.agent_finding import AgentFinding

    f1 = AgentFinding(
        school_id="school-1", finding_type="anomaly", severity="low",
        target_type="class", summary="s1", status="open",
        idempotency_key="dup-key",
    )
    f2 = AgentFinding(
        school_id="school-1", finding_type="anomaly", severity="low",
        target_type="class", summary="s2", status="open",
        idempotency_key="dup-key",
    )
    db.add(f1)
    await db.flush()
    db.add(f2)
    with pytest.raises(IntegrityError):
        await db.flush()


# ---------- AgentTask ----------

@pytest.mark.asyncio
async def test_create_agent_task(db):
    from edu_cloud.models.agent_finding import AgentTask

    task = AgentTask(
        school_id="school-1",
        finding_id=None,
        task_type="notify_parent",
        assignee_role="homeroom_teacher",
        payload={"message": "请关注学生数学成绩"},
        status="pending",
    )
    db.add(task)
    await db.flush()
    assert task.id is not None
    assert task.finding_id is None
    assert task.task_type == "notify_parent"
    assert task.assignee_role == "homeroom_teacher"
    assert task.payload["message"] == "请关注学生数学成绩"
    assert task.status == "pending"


# ---------- ScopeVersion ----------

@pytest.mark.asyncio
async def test_create_scope_version(db):
    from edu_cloud.models.scope_version import ScopeVersion

    sv = ScopeVersion(
        school_id="school-1",
        user_id="user-1",
        last_reason="新学期角色变更",
    )
    db.add(sv)
    await db.flush()
    assert sv.id is not None
    assert sv.version == 1
    assert sv.last_reason == "新学期角色变更"
    assert sv.created_at is not None
