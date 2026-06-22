"""Semester conduct evaluation report service.

Generates structured reports at class and school level,
including summary stats, student rankings, category breakdowns, and weekly trends.
"""
import logging
from datetime import date, timedelta

from sqlalchemy import select, func, case, outerjoin
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.school import School
from edu_cloud.modules.conduct.models import (
    ConductRecord, ConductRuleItem, ConductRuleCategory, ConductSemester,
)
from edu_cloud.services.conduct_workflow import Class, Student

logger = logging.getLogger(__name__)


async def generate_semester_report(
    db: AsyncSession,
    class_id: str,
    semester_id: str | None = None,
) -> dict:
    """Generate a structured semester conduct evaluation for a class.

    Args:
        db: Async database session.
        class_id: Target class ID.
        semester_id: Optional semester ID for date range. Falls back to
            current semester, then last 90 days.

    Returns:
        Dict with summary, top/bottom students, category breakdown, weekly trend.
    """
    # --- resolve date range and semester name ---
    semester_name = None
    start, end = await _resolve_date_range(db, class_id, semester_id)
    if semester_id:
        sem = await db.get(ConductSemester, semester_id)
        if sem:
            semester_name = sem.name
    else:
        # Try current semester
        sem = (await db.execute(
            select(ConductSemester).where(
                ConductSemester.class_id == class_id,
                ConductSemester.is_current.is_(True),
            )
        )).scalar_one_or_none()
        if sem:
            semester_name = sem.name

    # --- class name ---
    cls = await db.get(Class, class_id)
    class_name = cls.name if cls else "Unknown"

    # --- base filter: records in this class within date range ---
    base_filter = [
        ConductRecord.class_id == class_id,
        ConductRecord.date >= start,
        ConductRecord.date <= end,
    ]

    # --- summary ---
    total_records = (await db.execute(
        select(func.count(ConductRecord.id)).where(*base_filter)
    )).scalar() or 0

    distinct_students = (await db.execute(
        select(func.count(func.distinct(ConductRecord.student_id))).where(*base_filter)
    )).scalar() or 0

    positive_count = (await db.execute(
        select(func.count(ConductRecord.id)).where(
            *base_filter, ConductRecord.points > 0,
        )
    )).scalar() or 0

    # avg points per student
    if distinct_students > 0:
        total_points = (await db.execute(
            select(func.coalesce(func.sum(ConductRecord.points), 0)).where(*base_filter)
        )).scalar() or 0
        avg_points = round(total_points / distinct_students, 2)
    else:
        avg_points = 0.0

    positive_rate = round(positive_count / total_records, 4) if total_records > 0 else 0.0

    summary = {
        "total_students": distinct_students,
        "total_records": total_records,
        "avg_points": avg_points,
        "positive_rate": positive_rate,
    }

    # --- top / bottom students ---
    ranking_stmt = (
        select(
            Student.id.label("student_id"),
            Student.name,
            func.coalesce(func.sum(ConductRecord.points), 0).label("total"),
        )
        .join(ConductRecord, ConductRecord.student_id == Student.id)
        .where(*base_filter)
        .group_by(Student.id, Student.name)
    )
    rows_desc = (await db.execute(
        ranking_stmt.order_by(func.sum(ConductRecord.points).desc())
    )).all()

    top_students = []
    for rank, r in enumerate(rows_desc[:10], 1):
        top_students.append({"name": r.name, "points": int(r.total), "rank": rank})

    bottom_students = []
    rows_asc = list(reversed(rows_desc))
    for rank, r in enumerate(rows_asc[:10], 1):
        bottom_students.append({"name": r.name, "points": int(r.total), "rank": rank})

    # --- category breakdown ---
    category_breakdown = await _category_breakdown(db, base_filter)

    # --- weekly trend ---
    weekly_trend = await _weekly_trend(db, base_filter, start, end)

    return {
        "class_name": class_name,
        "semester_name": semester_name,
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "summary": summary,
        "top_students": top_students,
        "bottom_students": bottom_students,
        "category_breakdown": category_breakdown,
        "weekly_trend": weekly_trend,
    }


async def generate_school_report(
    db: AsyncSession,
    school_id: str,
    semester_id: str | None = None,
) -> dict:
    """Generate a school-wide semester conduct report aggregating all classes.

    Args:
        db: Async database session.
        school_id: Target school ID.
        semester_id: Optional semester ID for date filtering.

    Returns:
        Dict with school summary and per-class rankings.
    """
    school = await db.get(School, school_id)
    school_name = school.name if school else "Unknown"

    semester_name = None
    if semester_id:
        sem = await db.get(ConductSemester, semester_id)
        if sem:
            semester_name = sem.name

    # Fetch all classes in the school
    class_rows = (await db.execute(
        select(Class).where(Class.school_id == school_id).order_by(Class.name)
    )).scalars().all()

    total_students = 0
    total_records = 0
    total_points_sum = 0
    class_rankings = []

    for cls in class_rows:
        report = await generate_semester_report(db, cls.id, semester_id)
        s = report["summary"]
        total_students += s["total_students"]
        total_records += s["total_records"]
        total_points_sum += s["avg_points"] * s["total_students"]

        top_student_name = report["top_students"][0]["name"] if report["top_students"] else ""

        class_rankings.append({
            "class_name": report["class_name"],
            "avg_points": s["avg_points"],
            "record_count": s["total_records"],
            "top_student": top_student_name,
        })

    avg_points = round(total_points_sum / total_students, 2) if total_students > 0 else 0.0

    return {
        "school_name": school_name,
        "semester_name": semester_name,
        "summary": {
            "total_classes": len(class_rows),
            "total_students": total_students,
            "total_records": total_records,
            "avg_points": avg_points,
        },
        "class_rankings": class_rankings,
    }


# ═══════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════

async def _resolve_date_range(
    db: AsyncSession,
    class_id: str,
    semester_id: str | None,
) -> tuple[date, date]:
    """Resolve start/end dates from semester or default to last 90 days."""
    if semester_id:
        sem = await db.get(ConductSemester, semester_id)
        if sem:
            return sem.start_date, sem.end_date

    # Try current semester for this class
    sem = (await db.execute(
        select(ConductSemester).where(
            ConductSemester.class_id == class_id,
            ConductSemester.is_current.is_(True),
        )
    )).scalar_one_or_none()
    if sem:
        return sem.start_date, sem.end_date

    # Default: last 90 days
    today = date.today()
    return today - timedelta(days=90), today


async def _category_breakdown(db: AsyncSession, base_filter: list) -> list[dict]:
    """Group records by rule category, computing positive/negative counts and net points."""
    # LEFT JOIN ConductRecord → ConductRuleItem → ConductRuleCategory
    stmt = (
        select(
            func.coalesce(ConductRuleCategory.name, "其他").label("category"),
            func.count(
                case((ConductRecord.points > 0, ConductRecord.id))
            ).label("positive_count"),
            func.count(
                case((ConductRecord.points < 0, ConductRecord.id))
            ).label("negative_count"),
            func.coalesce(func.sum(ConductRecord.points), 0).label("net_points"),
        )
        .select_from(ConductRecord)
        .outerjoin(ConductRuleItem, ConductRecord.rule_item_id == ConductRuleItem.id)
        .outerjoin(ConductRuleCategory, ConductRuleItem.category_id == ConductRuleCategory.id)
        .where(*base_filter)
        .group_by(func.coalesce(ConductRuleCategory.name, "其他"))
        .order_by(func.coalesce(ConductRuleCategory.name, "其他"))
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "category": r.category,
            "positive_count": int(r.positive_count),
            "negative_count": int(r.negative_count),
            "net_points": int(r.net_points),
        }
        for r in rows
    ]


async def _weekly_trend(
    db: AsyncSession,
    base_filter: list,
    start: date,
    end: date,
) -> list[dict]:
    """Compute weekly positive/negative record counts across the date range.

    Same iteration pattern as scope_service._weekly_trend (iterating
    Monday-aligned weeks), but over the explicit start/end range.
    """
    # Align start to its Monday
    week_start = start - timedelta(days=start.weekday())
    trend = []

    while week_start <= end:
        we = week_start + timedelta(days=6)

        pos = (await db.execute(
            select(func.count(ConductRecord.id)).where(
                *base_filter,
                ConductRecord.date >= week_start,
                ConductRecord.date <= we,
                ConductRecord.points > 0,
            )
        )).scalar() or 0

        neg = (await db.execute(
            select(func.count(ConductRecord.id)).where(
                *base_filter,
                ConductRecord.date >= week_start,
                ConductRecord.date <= we,
                ConductRecord.points < 0,
            )
        )).scalar() or 0

        trend.append({
            "week_start": week_start.isoformat(),
            "positive": pos,
            "negative": neg,
        })

        week_start += timedelta(weeks=1)

    return trend
