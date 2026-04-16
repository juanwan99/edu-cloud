"""W6 patrol workflow — hourly anomaly scan: grading overdue, low submission, score anomalies, dedup dispatch."""
from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select

from edu_cloud.ai.workflow.engine import WorkflowContext
from edu_cloud.ai.workflow.registry import StepDefinition, WorkflowDefinition
from edu_cloud.models.agent_finding import AgentFinding
from edu_cloud.models.agent_snapshot import ClassExamReport
from edu_cloud.modules.exam.models import Exam
from edu_cloud.modules.grading.models import GradingTask
from edu_cloud.modules.homework.models import HomeworkSubmission, HomeworkTask

logger = logging.getLogger(__name__)


def _ensure_aware(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (assume UTC if naive)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# Thresholds
GRADING_OVERDUE_HOURS = 72
SUBMISSION_DEADLINE_WINDOW_HOURS = 24
SUBMISSION_LOW_THRESHOLD = 0.5  # 50%
ANOMALY_Z_THRESHOLD = 1.0
MAX_NOTIFICATIONS_PER_ROLE_PER_DAY = 10

# Non-terminal grading statuses (tasks still awaiting completion)
_GRADING_INCOMPLETE_STATUSES = {"pending", "in_progress", "running", "processing"}


# ---------------------------------------------------------------------------
# Step 1: scan_grading_overdue
# ---------------------------------------------------------------------------

async def scan_grading_overdue(ctx: WorkflowContext) -> dict:
    """Find GradingTask records that are >72h old and not completed."""
    db = ctx.db
    school_id = ctx.school_id
    today_str = date.today().isoformat()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=GRADING_OVERDUE_HOURS)

    tasks = (await db.execute(
        select(GradingTask).where(
            GradingTask.school_id == school_id,
            GradingTask.status.in_(_GRADING_INCOMPLETE_STATUSES),
            GradingTask.created_at < cutoff,
        )
    )).scalars().all()

    finding_count = 0
    for task in tasks:
        idem_key = f"grading:{task.id}:overdue:{today_str}"

        existing = (await db.execute(
            select(AgentFinding).where(AgentFinding.idempotency_key == idem_key)
        )).scalars().first()
        if existing is not None:
            continue

        hours_elapsed = (datetime.now(timezone.utc) - _ensure_aware(task.created_at)).total_seconds() / 3600
        finding = AgentFinding(
            school_id=school_id,
            finding_type="grading_overdue",
            severity="warning",
            target_type="grading_task",
            target_id=task.id,
            summary=f"阅卷任务已超时 {hours_elapsed:.0f} 小时（阈值 {GRADING_OVERDUE_HOURS}h）",
            detail={
                "task_id": task.id,
                "status": task.status,
                "hours_elapsed": round(hours_elapsed, 1),
            },
            status="new",
            notify_roles=["academic_director", "grade_leader"],
            idempotency_key=idem_key,
        )
        db.add(finding)
        finding_count += 1

    await db.flush()
    logger.info("scan_grading_overdue: %d findings for school %s", finding_count, school_id)
    return {"finding_count": finding_count}


# ---------------------------------------------------------------------------
# Step 2: scan_submission_low
# ---------------------------------------------------------------------------

async def scan_submission_low(ctx: WorkflowContext) -> dict:
    """Find active HomeworkTask with deadline within 24h and submission rate < 50%."""
    db = ctx.db
    school_id = ctx.school_id
    today_str = date.today().isoformat()
    now = datetime.now(timezone.utc)
    deadline_cutoff = now + timedelta(hours=SUBMISSION_DEADLINE_WINDOW_HOURS)

    # Active tasks with deadline approaching
    tasks = (await db.execute(
        select(HomeworkTask).where(
            HomeworkTask.school_id == school_id,
            HomeworkTask.status == "active",
            HomeworkTask.deadline.isnot(None),
            HomeworkTask.deadline <= deadline_cutoff,
            HomeworkTask.deadline > now,  # not yet past
        )
    )).scalars().all()

    finding_count = 0
    for task in tasks:
        # Count total and submitted
        total = (await db.execute(
            select(func.count()).select_from(HomeworkSubmission).where(
                HomeworkSubmission.task_id == task.id,
            )
        )).scalar() or 0

        if total == 0:
            continue

        submitted = (await db.execute(
            select(func.count()).select_from(HomeworkSubmission).where(
                HomeworkSubmission.task_id == task.id,
                HomeworkSubmission.status.in_({"submitted", "graded"}),
            )
        )).scalar() or 0

        rate = submitted / total
        if rate >= SUBMISSION_LOW_THRESHOLD:
            continue

        idem_key = f"homework:{task.id}:low_submission:{today_str}"
        existing = (await db.execute(
            select(AgentFinding).where(AgentFinding.idempotency_key == idem_key)
        )).scalars().first()
        if existing is not None:
            continue

        finding = AgentFinding(
            school_id=school_id,
            finding_type="low_submission",
            severity="warning",
            target_type="homework_task",
            target_id=task.id,
            summary=f"作业「{task.title}」提交率 {rate:.0%}（{submitted}/{total}），截止时间临近",
            detail={
                "task_id": task.id,
                "title": task.title,
                "submitted": submitted,
                "total": total,
                "rate": round(rate, 4),
                "deadline": task.deadline.isoformat() if task.deadline else None,
            },
            status="new",
            notify_roles=["homeroom_teacher", "subject_teacher"],
            idempotency_key=idem_key,
        )
        db.add(finding)
        finding_count += 1

    await db.flush()
    logger.info("scan_submission_low: %d findings for school %s", finding_count, school_id)
    return {"finding_count": finding_count}


# ---------------------------------------------------------------------------
# Step 3: scan_score_anomalies
# ---------------------------------------------------------------------------

async def scan_score_anomalies(ctx: WorkflowContext) -> dict:
    """Check recently completed exams for class-level score anomalies using ClassExamReport."""
    db = ctx.db
    school_id = ctx.school_id
    today_str = date.today().isoformat()

    # Find exams completed in last 7 days
    recent_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    recent_exams = (await db.execute(
        select(Exam).where(
            Exam.school_id == school_id,
            Exam.status == "completed",
            Exam.updated_at >= recent_cutoff,
        )
    )).scalars().all()

    finding_count = 0
    for exam in recent_exams:
        reports = (await db.execute(
            select(ClassExamReport).where(
                ClassExamReport.exam_id == exam.id,
                ClassExamReport.school_id == school_id,
            )
        )).scalars().all()

        if len(reports) < 2:
            continue

        class_avgs = [r.class_avg for r in reports]
        mean = statistics.mean(class_avgs)
        stdev = statistics.stdev(class_avgs)

        if stdev == 0:
            continue

        for report in reports:
            z = abs(report.class_avg - mean) / stdev
            if z <= ANOMALY_Z_THRESHOLD:
                continue

            idem_key = f"class:{report.class_id}:score_anomaly:{exam.id}:{today_str}"
            existing = (await db.execute(
                select(AgentFinding).where(AgentFinding.idempotency_key == idem_key)
            )).scalars().first()
            if existing is not None:
                continue

            direction = "below" if report.class_avg < mean else "above"
            finding = AgentFinding(
                school_id=school_id,
                finding_type="score_anomaly",
                severity="critical",
                target_type="class",
                target_id=report.class_id,
                summary=f"班级均分 {report.class_avg:.1f} 偏离年级均分 {mean:.1f}（{direction}，z={z:.2f}）",
                detail={
                    "class_avg": report.class_avg,
                    "grade_avg": round(mean, 2),
                    "stdev": round(stdev, 2),
                    "z_score": round(z, 2),
                    "exam_id": exam.id,
                },
                status="new",
                notify_roles=["academic_director", "grade_leader"],
                idempotency_key=idem_key,
            )
            db.add(finding)
            finding_count += 1

    await db.flush()
    logger.info("scan_score_anomalies: %d findings for school %s", finding_count, school_id)
    return {"finding_count": finding_count}


# ---------------------------------------------------------------------------
# Step 4: deduplicate_and_dispatch
# ---------------------------------------------------------------------------

async def deduplicate_and_dispatch(ctx: WorkflowContext) -> dict:
    """Read all 'new' findings for the school, limit to 10 per role per day, set status to 'notified'."""
    db = ctx.db
    school_id = ctx.school_id

    findings = (await db.execute(
        select(AgentFinding).where(
            AgentFinding.school_id == school_id,
            AgentFinding.status == "new",
        ).order_by(AgentFinding.created_at)
    )).scalars().all()

    # Pre-count today's already-notified findings per role so the daily cap
    # accounts for earlier patrol runs, not just the current batch.
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    already_notified = (await db.execute(
        select(AgentFinding).where(
            AgentFinding.school_id == school_id,
            AgentFinding.status == "notified",
            AgentFinding.updated_at >= today_start,
        )
    )).scalars().all()

    role_counts: dict[str, int] = defaultdict(int)
    for nf in already_notified:
        for role in (nf.notify_roles or []):
            role_counts[role] += 1
    notified_count = 0

    for f in findings:
        roles = f.notify_roles or []
        # Check if any role is still under the limit.
        # Design note (F3): A multi-role finding (e.g. ["academic_director", "grade_leader"])
        # increments counters for ALL its roles when notified, even if one role is already
        # at the limit.  This is intentional — we prefer delivering the finding to at least
        # one reachable role rather than blocking it entirely.
        can_notify = False
        for role in roles:
            if role_counts[role] < MAX_NOTIFICATIONS_PER_ROLE_PER_DAY:
                can_notify = True
                break

        if not can_notify:
            continue

        f.status = "notified"
        notified_count += 1
        for role in roles:
            role_counts[role] += 1

    await db.flush()
    logger.info(
        "deduplicate_and_dispatch: %d notified for school %s (role caps: %s)",
        notified_count, school_id, dict(role_counts),
    )
    return {"notified_count": notified_count}


# ---------------------------------------------------------------------------
# W6 Workflow Definition
# ---------------------------------------------------------------------------

W6_PATROL = WorkflowDefinition(
    name="patrol",
    steps=[
        StepDefinition(name="scan_grading_overdue", func=scan_grading_overdue),
        StepDefinition(name="scan_submission_low", func=scan_submission_low),
        StepDefinition(name="scan_score_anomalies", func=scan_score_anomalies),
        StepDefinition(name="deduplicate_and_dispatch", func=deduplicate_and_dispatch),
    ],
    max_retries=3,
)
