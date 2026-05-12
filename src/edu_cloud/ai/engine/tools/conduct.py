"""Conduct/behavior tools — Pydantic AI native (migrated from ai/tools/conduct.py).

F003 Hardening: scope checks via DataScope before every class/student operation.
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta

from pydantic_ai import RunContext
from sqlalchemy import select, func

from edu_cloud.ai.engine.agent_deps import AgentDeps
from edu_cloud.ai.engine.tool_wrapper import edu_tool

logger = logging.getLogger(__name__)

_CONDUCT_READ_ROLES = frozenset({
    "platform_admin", "academic_director", "grade_leader",
    "homeroom_teacher", "subject_teacher", "parent",
})
_CONDUCT_WRITE_ROLES = frozenset({
    "platform_admin", "academic_director", "homeroom_teacher",
})
_ANALYSIS_ROLES = frozenset({
    "platform_admin", "academic_director",
    "homeroom_teacher", "subject_teacher",
})


def _check_class_scope(scope, class_id: str) -> str | None:
    if scope.role == "parent":
        return f"class '{class_id}' not accessible to parent role"
    if scope.visible_class_ids is None:
        return None
    if class_id not in scope.visible_class_ids:
        return f"class '{class_id}' out of scope for role {scope.role}"
    return None


@edu_tool(name="get_conduct_rankings", module_code="conduct", domain="conduct", allowed_roles=_CONDUCT_READ_ROLES, sensitivity="school")
async def get_conduct_rankings(ctx: RunContext[AgentDeps], class_id: str, semester_id: str | None = None) -> str:
    """Get student conduct point rankings for a class."""
    scope = ctx.deps.data_scope
    if err := _check_class_scope(scope, class_id):
        return json.dumps({"error": err})

    from edu_cloud.modules.conduct.models import ConductRecord
    from edu_cloud.modules.student.models import Student

    async with ctx.deps.get_db() as db:
        q = (
            select(Student.id, Student.name, func.sum(ConductRecord.points).label("total"))
            .join(ConductRecord, ConductRecord.student_id == Student.id)
            .where(Student.class_id == class_id, ConductRecord.school_id == scope.school_id)
            .group_by(Student.id, Student.name)
            .order_by(func.sum(ConductRecord.points).desc())
        )
        if semester_id:
            q = q.where(ConductRecord.semester_id == semester_id)
        rows = (await db.execute(q)).all()
    rankings = [{"rank": i + 1, "student_id": r[0], "name": r[1], "total": float(r[2] or 0)} for i, r in enumerate(rows)]
    return json.dumps({"class_id": class_id, "rankings": rankings}, ensure_ascii=False, default=str)


@edu_tool(name="get_conduct_records", module_code="conduct", domain="conduct", allowed_roles=_CONDUCT_READ_ROLES, sensitivity="school")
async def get_conduct_records(ctx: RunContext[AgentDeps], class_id: str, student_id: str | None = None, limit: int = 20) -> str:
    """Get conduct point records for a class, optionally filtered by student."""
    scope = ctx.deps.data_scope
    if err := _check_class_scope(scope, class_id):
        return json.dumps({"error": err})

    from edu_cloud.modules.conduct.models import ConductRecord
    from edu_cloud.modules.student.models import Student

    async with ctx.deps.get_db() as db:
        q = (
            select(ConductRecord, Student.name)
            .join(Student, ConductRecord.student_id == Student.id)
            .where(ConductRecord.class_id == class_id, ConductRecord.school_id == scope.school_id)
            .order_by(ConductRecord.created_at.desc())
            .limit(limit)
        )
        if student_id:
            q = q.where(ConductRecord.student_id == student_id)
        rows = (await db.execute(q)).all()
    records = [{"id": r[0].id, "student_name": r[1], "points": r[0].points, "reason": r[0].reason, "date": str(r[0].record_date)} for r in rows]
    return json.dumps({"class_id": class_id, "records": records}, ensure_ascii=False, default=str)


@edu_tool(name="get_conduct_rules", module_code="conduct", domain="conduct", allowed_roles=_CONDUCT_READ_ROLES, sensitivity="school")
async def get_conduct_rules(ctx: RunContext[AgentDeps], class_id: str) -> str:
    """Get conduct rules (categories + items) for a class."""
    scope = ctx.deps.data_scope
    if err := _check_class_scope(scope, class_id):
        return json.dumps({"error": err})

    from edu_cloud.modules.conduct.rules_service import get_rules
    async with ctx.deps.get_db() as db:
        rules = await get_rules(db, class_id)
    return json.dumps(rules, ensure_ascii=False, default=str)


@edu_tool(
    name="add_conduct_points", module_code="conduct", domain="conduct",
    allowed_roles=_CONDUCT_WRITE_ROLES, risk_level="medium", is_read_only=False, sensitivity="school",
)
async def add_conduct_points(
    ctx: RunContext[AgentDeps], class_id: str, student_name: str, points: int, reason: str = "",
) -> str:
    """Add conduct points for a student (positive or negative)."""
    scope = ctx.deps.data_scope
    if err := _check_class_scope(scope, class_id):
        return json.dumps({"error": err})

    from edu_cloud.modules.conduct.models import ConductRecord
    from edu_cloud.modules.student.models import Student

    async with ctx.deps.get_db() as db:
        student = (await db.execute(
            select(Student).where(Student.name == student_name, Student.class_id == class_id, Student.school_id == scope.school_id)
        )).scalar_one_or_none()
        if not student:
            return json.dumps({"error": f"未找到学生: {student_name}"})
        record = ConductRecord(
            student_id=student.id, class_id=class_id, school_id=scope.school_id,
            points=points, reason=reason, operator_id=ctx.deps.user_id,
            record_date=date.today(),
        )
        db.add(record)
        await db.commit()
    return json.dumps({"status": "ok", "student": student_name, "points": points, "reason": reason}, ensure_ascii=False)


@edu_tool(name="get_class_conduct_overview", module_code="conduct", domain="conduct", allowed_roles=_CONDUCT_READ_ROLES, sensitivity="school")
async def get_class_conduct_overview(ctx: RunContext[AgentDeps], class_id: str) -> str:
    """Get conduct overview for a class (student count, total points, averages)."""
    scope = ctx.deps.data_scope
    if err := _check_class_scope(scope, class_id):
        return json.dumps({"error": err})

    from edu_cloud.modules.conduct.models import ConductRecord
    from edu_cloud.modules.student.models import Student

    async with ctx.deps.get_db() as db:
        student_count = (await db.execute(
            select(func.count(Student.id)).where(Student.class_id == class_id, Student.school_id == scope.school_id)
        )).scalar() or 0
        total_points = (await db.execute(
            select(func.sum(ConductRecord.points)).where(ConductRecord.class_id == class_id, ConductRecord.school_id == scope.school_id)
        )).scalar() or 0
    return json.dumps({
        "class_id": class_id, "student_count": student_count,
        "total_points": float(total_points), "avg_points": round(float(total_points) / max(student_count, 1), 2),
    }, ensure_ascii=False, default=str)


@edu_tool(name="get_student_conduct_summary", module_code="conduct", domain="conduct", allowed_roles=_CONDUCT_READ_ROLES, sensitivity="student")
async def get_student_conduct_summary(ctx: RunContext[AgentDeps], student_id: str) -> str:
    """Get conduct summary for a specific student."""
    from edu_cloud.modules.conduct.models import ConductRecord
    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        total = (await db.execute(
            select(func.sum(ConductRecord.points)).where(
                ConductRecord.student_id == student_id, ConductRecord.school_id == scope.school_id,
            )
        )).scalar() or 0
        count = (await db.execute(
            select(func.count(ConductRecord.id)).where(
                ConductRecord.student_id == student_id, ConductRecord.school_id == scope.school_id,
            )
        )).scalar() or 0
    return json.dumps({"student_id": student_id, "total_points": float(total), "record_count": count}, ensure_ascii=False, default=str)


@edu_tool(name="analyze_student_behavior", module_code="conduct", domain="conduct", allowed_roles=_ANALYSIS_ROLES, sensitivity="student")
async def analyze_student_behavior(ctx: RunContext[AgentDeps], student_id: str, days: int = 30) -> str:
    """Analyze a student's behavior trend over recent days."""
    from edu_cloud.modules.conduct.models import ConductRecord
    scope = ctx.deps.data_scope
    cutoff = date.today() - timedelta(days=days)
    async with ctx.deps.get_db() as db:
        records = (await db.execute(
            select(ConductRecord).where(
                ConductRecord.student_id == student_id, ConductRecord.school_id == scope.school_id,
                ConductRecord.record_date >= cutoff,
            ).order_by(ConductRecord.record_date)
        )).scalars().all()
    positive = sum(r.points for r in records if r.points > 0)
    negative = sum(r.points for r in records if r.points < 0)
    return json.dumps({
        "student_id": student_id, "days": days, "record_count": len(records),
        "positive_total": positive, "negative_total": negative, "net": positive + negative,
    }, ensure_ascii=False, default=str)


@edu_tool(name="get_class_behavior_insights", module_code="conduct", domain="conduct", allowed_roles=_CONDUCT_READ_ROLES, sensitivity="school")
async def get_class_behavior_insights(ctx: RunContext[AgentDeps], class_id: str, days: int = 30) -> str:
    """Get behavior insights for a class (hotspots, risk students)."""
    scope = ctx.deps.data_scope
    if err := _check_class_scope(scope, class_id):
        return json.dumps({"error": err})

    from edu_cloud.modules.conduct.models import ConductRecord
    from edu_cloud.modules.student.models import Student
    cutoff = date.today() - timedelta(days=days)
    async with ctx.deps.get_db() as db:
        rows = (await db.execute(
            select(ConductRecord, Student.name)
            .join(Student, ConductRecord.student_id == Student.id)
            .where(ConductRecord.class_id == class_id, ConductRecord.school_id == scope.school_id, ConductRecord.record_date >= cutoff)
        )).all()
    student_totals: dict[str, float] = {}
    for record, name in rows:
        student_totals[name] = student_totals.get(name, 0) + record.points
    risk = [{"name": n, "total": t} for n, t in sorted(student_totals.items(), key=lambda x: x[1]) if t < 0]
    return json.dumps({"class_id": class_id, "days": days, "risk_students": risk[:5], "total_records": len(rows)}, ensure_ascii=False, default=str)


ALL_TOOLS = [
    get_conduct_rankings, get_conduct_records, get_conduct_rules, add_conduct_points,
    get_class_conduct_overview, get_student_conduct_summary, analyze_student_behavior, get_class_behavior_insights,
]
