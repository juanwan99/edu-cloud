"""Scope-Adaptive conduct overview aggregation service.

Returns conduct overview data at the appropriate aggregation level
based on the caller's role scope: class, school, or district.
"""
import logging
from datetime import date, timedelta

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.school import School
from edu_cloud.modules.conduct.models import ConductRecord
from edu_cloud.modules.student.models import Student, Class

logger = logging.getLogger(__name__)


async def _weekly_trend(
    db: AsyncSession,
    class_ids: list[str],
    weeks: int,
) -> list[dict]:
    """Aggregate weekly positive/negative record counts for given class_ids."""
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    trend = []
    for i in range(weeks - 1, -1, -1):
        ws = week_start - timedelta(weeks=i)
        we = ws + timedelta(days=6)
        pos = (await db.execute(
            select(func.count(ConductRecord.id)).where(
                ConductRecord.class_id.in_(class_ids),
                ConductRecord.date >= ws,
                ConductRecord.date <= we,
                ConductRecord.points > 0,
            )
        )).scalar() or 0
        neg = (await db.execute(
            select(func.count(ConductRecord.id)).where(
                ConductRecord.class_id.in_(class_ids),
                ConductRecord.date >= ws,
                ConductRecord.date <= we,
                ConductRecord.points < 0,
            )
        )).scalar() or 0
        trend.append({
            "week_start": ws.isoformat(),
            "positive": pos,
            "negative": neg,
        })
    return trend


async def get_conduct_overview(
    db: AsyncSession,
    scope_type: str,
    scope_ids: list[str],
    weeks: int = 4,
) -> dict:
    """Return conduct overview data at the appropriate aggregation level.

    Args:
        db: Async database session.
        scope_type: One of "class", "school", "district".
        scope_ids: List of IDs matching scope_type (class_ids, school_ids, or district names).
        weeks: Number of weeks for trend data (class scope only).

    Returns:
        Dict with scope_type-specific shape (see module docstring / task spec).
    """
    if scope_type == "class":
        return await _class_overview(db, scope_ids, weeks)
    elif scope_type == "school":
        return await _school_overview(db, scope_ids)
    elif scope_type == "district":
        return await _district_overview(db, scope_ids)
    else:
        raise ValueError(f"Unknown scope_type: {scope_type}")


# ═══════════════════════════════════════════════════
# class scope
# ═══════════════════════════════════════════════════

async def _class_overview(
    db: AsyncSession,
    class_ids: list[str],
    weeks: int,
) -> dict:
    # --- summary ---
    student_count = (await db.execute(
        select(func.count(Student.id)).where(Student.class_id.in_(class_ids))
    )).scalar() or 0

    record_count = (await db.execute(
        select(func.count(ConductRecord.id)).where(ConductRecord.class_id.in_(class_ids))
    )).scalar() or 0

    pos_count = (await db.execute(
        select(func.count(ConductRecord.id)).where(
            ConductRecord.class_id.in_(class_ids),
            ConductRecord.points > 0,
        )
    )).scalar() or 0

    neg_count = (await db.execute(
        select(func.count(ConductRecord.id)).where(
            ConductRecord.class_id.in_(class_ids),
            ConductRecord.points < 0,
        )
    )).scalar() or 0

    # --- rankings (top 5 / bottom 5 by total points) ---
    ranking_stmt = (
        select(
            Student.name,
            func.coalesce(func.sum(ConductRecord.points), 0).label("total"),
        )
        .join(ConductRecord, ConductRecord.student_id == Student.id)
        .where(ConductRecord.class_id.in_(class_ids))
        .group_by(Student.id, Student.name)
    )
    rows = (await db.execute(ranking_stmt.order_by(func.sum(ConductRecord.points).desc()))).all()

    top = [{"name": r.name, "points": int(r.total)} for r in rows[:5]]
    bottom = [{"name": r.name, "points": int(r.total)} for r in rows[-5:]] if len(rows) > 5 else list(reversed(top))

    # --- trend (weekly positive/negative counts) ---
    trend = await _weekly_trend(db, class_ids, weeks)

    return {
        "scope_type": "class",
        "summary": {
            "total_students": student_count,
            "total_records": record_count,
            "total_positive": pos_count,
            "total_negative": neg_count,
        },
        "rankings": {"top": top, "bottom": bottom},
        "trend": trend,
    }


# ═══════════════════════════════════════════════════
# school scope
# ═══════════════════════════════════════════════════

async def _school_overview(db: AsyncSession, school_ids: list[str]) -> dict:
    # --- summary ---
    student_count = (await db.execute(
        select(func.count(Student.id)).where(Student.school_id.in_(school_ids))
    )).scalar() or 0

    # Total records across all classes in the school(s)
    class_id_stmt = select(Class.id).where(Class.school_id.in_(school_ids))
    class_ids_in_school = [r for r in (await db.execute(class_id_stmt)).scalars().all()]

    record_count = 0
    if class_ids_in_school:
        record_count = (await db.execute(
            select(func.count(ConductRecord.id)).where(
                ConductRecord.class_id.in_(class_ids_in_school)
            )
        )).scalar() or 0

    class_count = len(class_ids_in_school)

    # --- class comparison ---
    comparison = []
    if class_ids_in_school:
        comp_stmt = (
            select(
                Class.id.label("class_id"),
                Class.name.label("class_name"),
                func.count(ConductRecord.id).label("record_count"),
                func.coalesce(func.avg(ConductRecord.points), 0.0).label("avg_points"),
            )
            .outerjoin(ConductRecord, ConductRecord.class_id == Class.id)
            .where(Class.school_id.in_(school_ids))
            .group_by(Class.id, Class.name)
            .order_by(Class.name)
        )
        rows = (await db.execute(comp_stmt)).all()
        comparison = [
            {
                "class_id": r.class_id,
                "class_name": r.class_name,
                "record_count": int(r.record_count),
                "avg_points": round(float(r.avg_points), 2),
            }
            for r in rows
        ]

    # Weekly trend (aggregate all classes in school)
    trend = await _weekly_trend(db, class_ids_in_school, 4) if class_ids_in_school else []

    return {
        "scope_type": "school",
        "summary": {
            "total_students": student_count,
            "total_records": record_count,
            "class_count": class_count,
        },
        "class_comparison": comparison,
        "trend": trend,
    }


# ═══════════════════════════════════════════════════
# district scope
# ═══════════════════════════════════════════════════

async def _district_overview(db: AsyncSession, district_names: list[str]) -> dict:
    # --- schools in district ---
    school_stmt = (
        select(School.id, School.name)
        .where(School.district.in_(district_names), School.is_active.is_(True))
    )
    schools = (await db.execute(school_stmt)).all()
    school_ids = [s.id for s in schools]
    school_name_map = {s.id: s.name for s in schools}

    total_students = 0
    school_comparison = []

    if school_ids:
        total_students = (await db.execute(
            select(func.count(Student.id)).where(Student.school_id.in_(school_ids))
        )).scalar() or 0

        # Per-school comparison
        comp_stmt = (
            select(
                Student.school_id,
                func.count(func.distinct(Student.id)).label("total_students"),
            )
            .where(Student.school_id.in_(school_ids))
            .group_by(Student.school_id)
        )
        student_counts = {r.school_id: int(r.total_students) for r in (await db.execute(comp_stmt)).all()}

        # Record stats per school (join via class)
        record_stmt = (
            select(
                Class.school_id,
                func.count(ConductRecord.id).label("record_count"),
                func.coalesce(func.avg(ConductRecord.points), 0.0).label("avg_points"),
            )
            .join(ConductRecord, ConductRecord.class_id == Class.id)
            .where(Class.school_id.in_(school_ids))
            .group_by(Class.school_id)
        )
        record_stats = {
            r.school_id: {"record_count": int(r.record_count), "avg_points": round(float(r.avg_points), 2)}
            for r in (await db.execute(record_stmt)).all()
        }

        for sid in school_ids:
            school_comparison.append({
                "school_id": sid,
                "school_name": school_name_map[sid],
                "total_students": student_counts.get(sid, 0),
                "record_count": record_stats.get(sid, {}).get("record_count", 0),
                "avg_points": record_stats.get(sid, {}).get("avg_points", 0.0),
            })

    # Weekly trend (aggregate all classes across all schools in district)
    all_class_ids: list[str] = []
    if school_ids:
        cls_stmt = select(Class.id).where(Class.school_id.in_(school_ids))
        all_class_ids = [r for r in (await db.execute(cls_stmt)).scalars().all()]
    trend = await _weekly_trend(db, all_class_ids, 4) if all_class_ids else []

    return {
        "scope_type": "district",
        "summary": {
            "total_schools": len(school_ids),
            "total_students": total_students,
        },
        "school_comparison": school_comparison,
        "trend": trend,
    }
