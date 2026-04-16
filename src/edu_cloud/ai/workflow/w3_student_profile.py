"""W3 student profile — Steps 1-4: mastery update + trend + class weakness + learning advice."""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from edu_cloud.ai.workflow.engine import WorkflowContext
from edu_cloud.models.agent_finding import AgentFinding, AgentTask
from edu_cloud.modules.exam.models import ExamResult
from edu_cloud.modules.profile.models import StudentExamSnapshot, StudentKnowledgeMastery
from edu_cloud.modules.student.models import Student

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Step 1: update_knowledge_mastery
# ---------------------------------------------------------------------------

async def update_knowledge_mastery(ctx: WorkflowContext) -> dict:
    """Incrementally update StudentKnowledgeMastery from exam results.

    Reads ExamResults for the triggered exam. For each result that contains
    ``knowledge_scores`` in its ``detail_scores`` JSON, upserts mastery records.
    Returns ``{"updated_count": N}``.
    """
    db = ctx.db
    exam_id = ctx.trigger_ref
    school_id = ctx.school_id

    results = (await db.execute(
        select(ExamResult).where(
            ExamResult.exam_id == exam_id,
            ExamResult.school_id == school_id,
        )
    )).scalars().all()

    updated_count = 0
    now = datetime.now(timezone.utc)

    for r in results:
        if not r.detail_scores or "knowledge_scores" not in r.detail_scores:
            continue

        knowledge_scores: dict = r.detail_scores["knowledge_scores"]
        if not isinstance(knowledge_scores, dict):
            continue

        for kp_id, score_data in knowledge_scores.items():
            if not isinstance(score_data, dict):
                continue

            score_val = score_data.get("score", 0)
            max_val = score_data.get("max", 1.0)
            rate = score_val / max_val if max_val > 0 else 0.0

            # Look up existing mastery record
            existing = (await db.execute(
                select(StudentKnowledgeMastery).where(
                    StudentKnowledgeMastery.student_id == r.student_id,
                    StudentKnowledgeMastery.knowledge_point_id == kp_id,
                )
            )).scalars().first()

            if existing:
                # F3: Skip if this exam was already processed (idempotent per exam)
                if existing.last_exam_id == exam_id:
                    continue

                existing.attempt_count += 1
                if rate >= 0.6:
                    existing.correct_count += 1
                elif rate >= 0.3:
                    existing.partial_count += 1

                # Recalculate mastery as weighted average (recent scores weigh more)
                recent = existing.recent_scores or []
                recent.append(rate)
                recent = recent[-10:]  # keep last 10
                existing.recent_scores = recent

                # EMA-style: newer scores weighted heavier
                if len(recent) == 1:
                    existing.mastery_level = rate
                else:
                    alpha = 0.4
                    ema = recent[0]
                    for s in recent[1:]:
                        ema = alpha * s + (1 - alpha) * ema
                    existing.mastery_level = round(ema, 4)

                # Confidence grows with attempts (caps at 1.0)
                existing.confidence = round(min(1.0, 0.3 + 0.1 * existing.attempt_count), 2)

                # Trend detection
                if len(recent) >= 3:
                    first_half = recent[: len(recent) // 2]
                    second_half = recent[len(recent) // 2:]
                    avg_first = sum(first_half) / len(first_half)
                    avg_second = sum(second_half) / len(second_half)
                    if avg_second - avg_first > 0.05:
                        existing.trend = "improving"
                    elif avg_first - avg_second > 0.05:
                        existing.trend = "declining"
                    else:
                        existing.trend = "stable"

                existing.last_exam_id = exam_id
                existing.last_exam_date = now
            else:
                # New record
                mastery = StudentKnowledgeMastery(
                    student_id=r.student_id,
                    knowledge_point_id=kp_id,
                    mastery_level=round(rate, 4),
                    confidence=0.3,
                    attempt_count=1,
                    correct_count=1 if rate >= 0.6 else 0,
                    partial_count=1 if 0.3 <= rate < 0.6 else 0,
                    trend="stable",
                    recent_scores=[rate],
                    last_exam_id=exam_id,
                    last_exam_date=now,
                    school_id=school_id,
                )
                db.add(mastery)

            updated_count += 1

    await db.flush()
    logger.info("update_knowledge_mastery: %d updates for exam %s", updated_count, exam_id)
    return {"updated_count": updated_count}


# ---------------------------------------------------------------------------
# Step 2: update_student_profiles
# ---------------------------------------------------------------------------

async def update_student_profiles(ctx: WorkflowContext) -> dict:
    """Enrich StudentExamSnapshot with trend data from historical snapshots.

    For each snapshot of the current exam, queries the student's last 10 exams
    in the same subject and computes trend / exam_count, storing them in the
    ``error_summary`` JSON field.
    Returns ``{"profile_count": N}``.
    """
    db = ctx.db
    exam_id = ctx.trigger_ref
    school_id = ctx.school_id

    # Get snapshots for this exam
    snapshots = (await db.execute(
        select(StudentExamSnapshot).where(
            StudentExamSnapshot.exam_id == exam_id,
            StudentExamSnapshot.school_id == school_id,
        )
    )).scalars().all()

    if not snapshots:
        return {"profile_count": 0}

    profile_count = 0

    for snap in snapshots:
        # Query history: last 10 exams, same student + subject_code
        # Order by exam_date (preferred) then created_at as fallback
        # NOTE (F5): This query does not exclude future exam dates. When
        # backfilling old exams, the trend may include exams that hadn't
        # occurred yet at the time of the exam being processed. The primary
        # use case is processing the latest exam; backfill accuracy is a
        # known limitation.
        history = (await db.execute(
            select(StudentExamSnapshot)
            .where(
                StudentExamSnapshot.student_id == snap.student_id,
                StudentExamSnapshot.subject_code == snap.subject_code,
                StudentExamSnapshot.school_id == school_id,
            )
            .order_by(
                StudentExamSnapshot.exam_date.desc().nulls_last(),
                StudentExamSnapshot.created_at.desc(),
            )
            .limit(10)
        )).scalars().all()

        # Build trend data from score_rate history (oldest first)
        rates = [h.score_rate for h in reversed(history)]
        exam_count = len(rates)

        # Determine trend direction
        if exam_count >= 2:
            first_half = rates[: exam_count // 2]
            second_half = rates[exam_count // 2:]
            avg_first = sum(first_half) / len(first_half)
            avg_second = sum(second_half) / len(second_half)
            if avg_second - avg_first > 0.02:
                trend = "improving"
            elif avg_first - avg_second > 0.02:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"

        # Merge into error_summary (preserve existing keys)
        existing_summary = snap.error_summary or {}
        existing_summary["trend"] = trend
        existing_summary["exam_count"] = exam_count
        existing_summary["score_rates"] = rates
        snap.error_summary = existing_summary

        profile_count += 1

    await db.flush()
    logger.info("update_student_profiles: %d profiles enriched for exam %s", profile_count, exam_id)
    return {"profile_count": profile_count}


# ---------------------------------------------------------------------------
# Step 3: compute_class_weakness
# ---------------------------------------------------------------------------

async def compute_class_weakness(ctx: WorkflowContext) -> dict:
    """Aggregate weak knowledge points per class and create AgentFinding records.

    Reads StudentKnowledgeMastery where mastery_level < 0.4, groups by class
    (joining with Student to get class_id), and stores results as AgentFinding
    records with finding_type="class_weakness".
    Returns ``{"class_count": N}``.
    """
    db = ctx.db
    school_id = ctx.school_id

    # Find all low-mastery records for this school, joined with student for class_id
    stmt = (
        select(StudentKnowledgeMastery, Student.class_id)
        .join(Student, Student.id == StudentKnowledgeMastery.student_id)
        .where(
            StudentKnowledgeMastery.school_id == school_id,
            StudentKnowledgeMastery.mastery_level < 0.4,
            Student.class_id.is_not(None),
        )
    )
    rows = (await db.execute(stmt)).all()

    if not rows:
        return {"class_count": 0}

    # Group weak knowledge points by class_id
    class_weaknesses: dict[str, list[dict]] = defaultdict(list)
    for mastery, class_id in rows:
        class_weaknesses[class_id].append({
            "knowledge_point_id": mastery.knowledge_point_id,
            "student_id": mastery.student_id,
            "mastery_level": mastery.mastery_level,
        })

    # Create AgentFinding per class (idempotent via idempotency_key)
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    for class_id, weak_points in class_weaknesses.items():
        idem_key = f"class_weakness:{school_id}:{class_id}:{date_str}"

        existing = (await db.execute(
            select(AgentFinding).where(AgentFinding.idempotency_key == idem_key)
        )).scalars().first()

        if existing:
            # Update detail with latest data
            existing.detail = {"weak_points": weak_points}
            continue

        finding = AgentFinding(
            finding_type="class_weakness",
            severity="info",
            target_type="class",
            target_id=class_id,
            summary=f"班级有 {len(weak_points)} 个薄弱知识点（掌握度 < 0.4）",
            detail={"weak_points": weak_points},
            status="open",
            notify_roles=["homeroom_teacher", "subject_teacher"],
            idempotency_key=idem_key,
            school_id=school_id,
        )
        db.add(finding)

    await db.flush()
    class_count = len(class_weaknesses)
    logger.info("compute_class_weakness: %d classes with weakness in school %s", class_count, school_id)
    return {"class_count": class_count}


# ---------------------------------------------------------------------------
# Step 4: generate_learning_advice
# ---------------------------------------------------------------------------

_MAX_ADVICE_PER_RUN = 100


async def generate_learning_advice(ctx: WorkflowContext) -> dict:
    """Template-based learning advice for students with low mastery.

    Reads students with mastery_level < 0.4, creates AgentTask records
    (task_type="learning_advice", assignee_role="homeroom_teacher").
    Limit: max 100 per run.
    Returns ``{"advice_count": N}``.
    """
    db = ctx.db
    school_id = ctx.school_id

    # Find distinct students with low mastery
    stmt = (
        select(
            StudentKnowledgeMastery.student_id,
            Student.name.label("student_name"),
            Student.class_id,
        )
        .join(Student, Student.id == StudentKnowledgeMastery.student_id)
        .where(
            StudentKnowledgeMastery.school_id == school_id,
            StudentKnowledgeMastery.mastery_level < 0.4,
        )
        .group_by(
            StudentKnowledgeMastery.student_id,
            Student.name,
            Student.class_id,
        )
        .limit(_MAX_ADVICE_PER_RUN)
    )
    rows = (await db.execute(stmt)).all()

    if not rows:
        return {"advice_count": 0}

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    advice_count = 0

    for row in rows:
        student_id = row.student_id
        student_name = row.student_name

        # Idempotency: one task per student per day
        idem_key = f"learning_advice:{school_id}:{student_id}:{date_str}"
        # F4: Filter by today's date so idempotency is truly per-day, not forever
        existing = (await db.execute(
            select(AgentTask).where(
                AgentTask.task_type == "learning_advice",
                AgentTask.school_id == school_id,
                AgentTask.payload["student_id"].as_string() == student_id,
                AgentTask.payload["generated_at"].as_string() == date_str,
            )
        )).scalars().first()

        if existing:
            continue

        # Template-based advice (no LLM call)
        task = AgentTask(
            task_type="learning_advice",
            assignee_role="homeroom_teacher",
            payload={
                "student_id": student_id,
                "student_name": student_name,
                "class_id": row.class_id,
                "advice": f"学生 {student_name} 存在知识薄弱点（掌握度 < 0.4），建议关注并安排针对性辅导。",
                "generated_at": date_str,
            },
            status="pending",
            school_id=school_id,
        )
        db.add(task)
        advice_count += 1

    await db.flush()
    logger.info("generate_learning_advice: %d advice tasks for school %s", advice_count, school_id)
    return {"advice_count": advice_count}


# ---------------------------------------------------------------------------
# W3 Workflow Definition
# ---------------------------------------------------------------------------

from edu_cloud.ai.workflow.registry import WorkflowDefinition, StepDefinition  # noqa: E402

W3_STUDENT_PROFILE = WorkflowDefinition(
    name="student_profile",
    steps=[
        StepDefinition(name="update_knowledge_mastery", func=update_knowledge_mastery),
        StepDefinition(name="update_student_profiles", func=update_student_profiles),
        StepDefinition(name="compute_class_weakness", func=compute_class_weakness),
        StepDefinition(name="generate_learning_advice", func=generate_learning_advice),
    ],
    max_retries=3,
)
