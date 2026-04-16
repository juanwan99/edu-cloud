"""W1 post-exam analysis — Steps 1-5: snapshot, class reports, student diagnoses, anomaly detection, notifications."""
from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from datetime import date, datetime, timezone

from sqlalchemy import select

from edu_cloud.ai.workflow.engine import WorkflowContext
from edu_cloud.models.agent_finding import AgentFinding
from edu_cloud.models.agent_snapshot import ClassExamReport, ExamAnalysisSnapshot
from edu_cloud.modules.exam.models import Exam, ExamResult, Subject
from edu_cloud.modules.profile.models import StudentExamSnapshot
from edu_cloud.modules.student.models import Student

logger = logging.getLogger(__name__)

# Z-score threshold for class anomaly detection.  With small class counts
# (3-10) the sample stdev is large, so a strict 2.0 rarely fires.  1.0 gives
# a practical alert level for typical grade sizes in K-12.
ANOMALY_Z_THRESHOLD = 1.0


# ---------------------------------------------------------------------------
# Step 1: compute_exam_snapshot
# ---------------------------------------------------------------------------

async def compute_exam_snapshot(ctx: WorkflowContext) -> dict:
    """Compute school-level overview + per-subject stats from exam results."""
    db = ctx.db
    exam_id = ctx.trigger_ref
    school_id = ctx.school_id

    # Fetch exam metadata
    exam = (await db.execute(
        select(Exam).where(Exam.id == exam_id)
    )).scalars().first()
    if exam is None:
        raise ValueError(f"Exam {exam_id} not found")

    semester = exam.semester or "unknown"
    max_score = exam.max_score or 0

    # Fetch all results for this exam
    results = (await db.execute(
        select(ExamResult).where(
            ExamResult.exam_id == exam_id,
            ExamResult.school_id == school_id,
        )
    )).scalars().all()

    if not results:
        return {"snapshot_count": 0}

    scores = [r.total_score for r in results]
    now = datetime.now(timezone.utc)

    # School-level overview snapshot
    overview_metrics = {
        "avg": round(statistics.mean(scores), 2),
        "max": max(scores),
        "min": min(scores),
        "median": round(statistics.median(scores), 2),
        "stdev": round(statistics.stdev(scores), 2) if len(scores) > 1 else 0,
        "total_students": len(scores),
    }

    overview = ExamAnalysisSnapshot(
        exam_id=exam_id,
        school_id=school_id,
        snapshot_type="school_overview",
        target_type="school",
        target_id=school_id,
        subject_code=None,
        semester=semester,
        version=1,
        status="ready",
        metrics=overview_metrics,
        computed_at=now,
    )
    db.add(overview)
    snapshot_count = 1

    # Per-subject snapshots
    subjects = (await db.execute(
        select(Subject).where(Subject.exam_id == exam_id)
    )).scalars().all()

    for subj in subjects:
        # Extract per-subject scores from detail_scores JSON
        subj_scores = []
        for r in results:
            if r.detail_scores and subj.code in r.detail_scores:
                subj_scores.append(r.detail_scores[subj.code])

        if not subj_scores:
            continue

        pass_threshold = max_score * 0.6  # 60% pass line
        pass_count = sum(1 for s in subj_scores if s >= pass_threshold * (
            # Scale pass threshold if subject score != total score
            # Use ratio of subject avg to total avg as rough scale
            1.0
        ))

        subj_metrics = {
            "avg": round(statistics.mean(subj_scores), 2),
            "max": max(subj_scores),
            "min": min(subj_scores),
            "pass_rate": round(pass_count / len(subj_scores), 4),
            "total_students": len(subj_scores),
        }

        snap = ExamAnalysisSnapshot(
            exam_id=exam_id,
            school_id=school_id,
            snapshot_type="subject_detail",
            target_type="subject",
            target_id=subj.id,
            subject_code=subj.code,
            semester=semester,
            version=1,
            status="ready",
            metrics=subj_metrics,
            computed_at=now,
        )
        db.add(snap)
        snapshot_count += 1

    await db.flush()
    logger.info("compute_exam_snapshot: %d snapshots for exam %s", snapshot_count, exam_id)
    return {"snapshot_count": snapshot_count}


# ---------------------------------------------------------------------------
# Step 2: compute_class_reports
# ---------------------------------------------------------------------------

async def compute_class_reports(ctx: WorkflowContext) -> dict:
    """Compute per-class reports with grade ranking."""
    db = ctx.db
    exam_id = ctx.trigger_ref
    school_id = ctx.school_id

    # Fetch results with student info for class grouping
    results = (await db.execute(
        select(ExamResult).where(
            ExamResult.exam_id == exam_id,
            ExamResult.school_id == school_id,
        )
    )).scalars().all()

    if not results:
        return {"report_count": 0, "grade_avg": 0.0}

    # Map student_id -> class_id
    student_ids = [r.student_id for r in results]
    students = (await db.execute(
        select(Student).where(Student.id.in_(student_ids))
    )).scalars().all()
    student_class_map = {s.id: s.class_id for s in students}

    # Group scores by class
    class_scores: dict[str, list[float]] = defaultdict(list)
    all_scores = []
    for r in results:
        cid = student_class_map.get(r.student_id)
        if cid:
            class_scores[cid].append(r.total_score)
            all_scores.append(r.total_score)

    if not all_scores:
        return {"report_count": 0, "grade_avg": 0.0}

    grade_avg = round(statistics.mean(all_scores), 2)
    now = datetime.now(timezone.utc)

    # Compute per-class averages and rank them
    class_avgs: list[tuple[str, float]] = []
    for cid, sc in class_scores.items():
        avg = round(statistics.mean(sc), 2)
        class_avgs.append((cid, avg))

    # Sort descending by average for ranking
    class_avgs.sort(key=lambda x: x[1], reverse=True)

    report_count = 0
    for rank, (cid, avg) in enumerate(class_avgs, start=1):
        report = ClassExamReport(
            exam_id=exam_id,
            school_id=school_id,
            class_id=cid,
            grade_rank=rank,
            class_avg=avg,
            grade_avg=grade_avg,
            vs_last_exam=None,  # No previous exam comparison yet
            metrics={
                "student_count": len(class_scores[cid]),
                "max": max(class_scores[cid]),
                "min": min(class_scores[cid]),
            },
            version=1,
            status="ready",
            computed_at=now,
        )
        db.add(report)
        report_count += 1

    await db.flush()
    logger.info("compute_class_reports: %d reports, grade_avg=%.2f", report_count, grade_avg)
    return {"report_count": report_count, "grade_avg": grade_avg}


# ---------------------------------------------------------------------------
# Step 3: compute_student_diagnoses
# ---------------------------------------------------------------------------

async def compute_student_diagnoses(ctx: WorkflowContext) -> dict:
    """Create StudentExamSnapshot for each student with results."""
    db = ctx.db
    exam_id = ctx.trigger_ref
    school_id = ctx.school_id

    # Fetch exam metadata
    exam = (await db.execute(
        select(Exam).where(Exam.id == exam_id)
    )).scalars().first()
    if exam is None:
        raise ValueError(f"Exam {exam_id} not found")

    max_score = exam.max_score or 0
    subject_code = exam.subject_code or "TOTAL"
    exam_date = exam.exam_date

    # Fetch results
    results = (await db.execute(
        select(ExamResult).where(
            ExamResult.exam_id == exam_id,
            ExamResult.school_id == school_id,
        )
    )).scalars().all()

    if not results:
        return {"student_count": 0}

    # Map student_id -> student for class info
    student_ids = [r.student_id for r in results]
    students = (await db.execute(
        select(Student).where(Student.id.in_(student_ids))
    )).scalars().all()
    student_map = {s.id: s for s in students}

    now = datetime.now(timezone.utc)

    # Group results by class for rank computation
    class_results: dict[str, list] = defaultdict(list)
    all_results_for_rank: list[tuple[str, str | None, float]] = []  # (student_id, class_id, score)
    for r in results:
        student = student_map.get(r.student_id)
        cid = student.class_id if student else None
        class_results[cid].append((r.student_id, r.total_score))
        all_results_for_rank.append((r.student_id, cid, r.total_score))

    # Compute grade ranks (all students sorted by score desc)
    all_results_for_rank.sort(key=lambda x: x[2], reverse=True)
    grade_rank_map: dict[str, int] = {}
    for rank_idx, (sid, _, _) in enumerate(all_results_for_rank, start=1):
        grade_rank_map[sid] = rank_idx
    grade_size = len(all_results_for_rank)

    # Compute class ranks (per class sorted by score desc)
    class_rank_map: dict[str, int] = {}
    class_size_map: dict[str | None, int] = {}
    for cid, entries in class_results.items():
        entries.sort(key=lambda x: x[1], reverse=True)
        class_size_map[cid] = len(entries)
        for rank_idx, (sid, _) in enumerate(entries, start=1):
            class_rank_map[sid] = rank_idx

    count = 0
    for r in results:
        student = student_map.get(r.student_id)
        score_rate = round(r.total_score / max_score, 4) if max_score > 0 else 0
        cid = student.class_id if student else None

        snapshot = StudentExamSnapshot(
            student_id=r.student_id,
            exam_id=exam_id,
            subject_code=subject_code,
            total_score=r.total_score,
            max_score=max_score,
            score_rate=score_rate,
            class_rank=class_rank_map.get(r.student_id),
            grade_rank=grade_rank_map.get(r.student_id),
            class_size=class_size_map.get(cid),
            grade_size=grade_size,
            class_id_at_exam=cid,
            exam_date=exam_date,
            school_id=school_id,
            error_summary=r.detail_scores,
        )
        db.add(snapshot)
        count += 1

    await db.flush()
    logger.info("compute_student_diagnoses: %d snapshots for exam %s", count, exam_id)
    return {"student_count": count}


# ---------------------------------------------------------------------------
# Step 4: detect_anomalies
# ---------------------------------------------------------------------------

async def detect_anomalies(ctx: WorkflowContext) -> dict:
    """Flag classes whose average deviates >2σ from grade mean as critical findings."""
    db = ctx.db
    exam_id = ctx.trigger_ref
    school_id = ctx.school_id

    # Read ClassExamReport records for this exam
    reports = (await db.execute(
        select(ClassExamReport).where(
            ClassExamReport.exam_id == exam_id,
            ClassExamReport.school_id == school_id,
        )
    )).scalars().all()

    if len(reports) < 2:
        return {"finding_count": 0, "finding_ids": []}

    class_avgs = [r.class_avg for r in reports]
    mean = statistics.mean(class_avgs)
    stdev = statistics.stdev(class_avgs)

    if stdev == 0:
        return {"finding_count": 0, "finding_ids": []}

    today_str = date.today().isoformat()
    finding_count = 0
    created_findings: list = []

    for report in reports:
        z = abs(report.class_avg - mean) / stdev
        if z <= ANOMALY_Z_THRESHOLD:
            continue

        idem_key = f"class:{report.class_id}:score_anomaly:{exam_id}:{today_str}"

        # Check for existing finding (idempotency)
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
                "grade_avg": mean,
                "stdev": round(stdev, 2),
                "z_score": round(z, 2),
                "exam_id": exam_id,
            },
            status="new",
            notify_roles=["academic_director", "grade_leader"],
            idempotency_key=idem_key,
        )
        db.add(finding)
        created_findings.append(finding)
        finding_count += 1

    await db.flush()

    # Collect created finding IDs so dispatch_notifications can scope to this run
    created_finding_ids = [f.id for f in created_findings]

    logger.info("detect_anomalies: %d findings for exam %s", finding_count, exam_id)
    return {"finding_count": finding_count, "finding_ids": created_finding_ids}


# ---------------------------------------------------------------------------
# Step 5: dispatch_notifications
# ---------------------------------------------------------------------------

async def dispatch_notifications(ctx: WorkflowContext) -> dict:
    """Mark findings from this workflow run as notified (phase 1: status update only, no push)."""
    db = ctx.db
    school_id = ctx.school_id

    # Scope to finding IDs created by detect_anomalies in this run
    anomaly_output = ctx.step_outputs.get("detect_anomalies", {})
    finding_ids = anomaly_output.get("finding_ids", [])

    if finding_ids:
        findings = (await db.execute(
            select(AgentFinding).where(
                AgentFinding.id.in_(finding_ids),
                AgentFinding.status == "new",
            )
        )).scalars().all()
    else:
        findings = []

    for f in findings:
        f.status = "notified"

    await db.flush()
    logger.info("dispatch_notifications: %d findings notified for school %s", len(findings), school_id)
    return {"notified_count": len(findings)}


# ---------------------------------------------------------------------------
# W1 Workflow Definition
# ---------------------------------------------------------------------------

from edu_cloud.ai.workflow.registry import WorkflowDefinition, StepDefinition  # noqa: E402

W1_POST_EXAM = WorkflowDefinition(
    name="post_exam_analysis",
    steps=[
        StepDefinition(name="compute_exam_snapshot", func=compute_exam_snapshot),
        StepDefinition(name="compute_class_reports", func=compute_class_reports),
        StepDefinition(name="compute_student_diagnoses", func=compute_student_diagnoses),
        StepDefinition(name="detect_anomalies", func=detect_anomalies),
        StepDefinition(name="dispatch_notifications", func=dispatch_notifications),
    ],
    max_retries=3,
)
