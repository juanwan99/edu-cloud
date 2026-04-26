"""TeachingPlan CRUD service (WP-E).

Canonical model: edu_cloud.models.teaching_plan.TeachingPlan
Service placed in calendar module per design intent (S4 expansion point).
"""
import logging

from sqlalchemy import select, delete as sa_delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.teaching_plan import TeachingPlan
from edu_cloud.services.exceptions import NotFoundError, ValidationError, ConflictError

logger = logging.getLogger(__name__)

REQUIRED_WEEK_FIELDS = {"week_number", "topic", "knowledge_points", "notes"}


def _validate_weeks_json(weeks_json: list) -> None:
    """Validate weeks_json structure: list of dicts with required fields."""
    if not isinstance(weeks_json, list):
        raise ValidationError("weeks_json 必须是数组")
    for i, week in enumerate(weeks_json):
        if not isinstance(week, dict):
            raise ValidationError(f"weeks_json[{i}] 必须是对象")
        missing = REQUIRED_WEEK_FIELDS - set(week.keys())
        if missing:
            raise ValidationError(f"weeks_json[{i}] 缺少字段: {', '.join(sorted(missing))}")
        if not isinstance(week["week_number"], int):
            raise ValidationError(f"weeks_json[{i}].week_number 必须是整数")
        if not isinstance(week["knowledge_points"], list):
            raise ValidationError(f"weeks_json[{i}].knowledge_points 必须是数组")


def _plan_summary(plan: TeachingPlan) -> dict:
    """Return plan dict for list view (no full weeks_json)."""
    return {
        "id": plan.id,
        "school_id": plan.school_id,
        "subject_code": plan.subject_code,
        "grade_id": plan.grade_id,
        "semester": plan.semester,
        "weeks_count": len(plan.weeks_json) if plan.weeks_json else 0,
        "created_by": plan.created_by,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
    }


def _plan_detail(plan: TeachingPlan) -> dict:
    """Return plan dict with full weeks_json."""
    d = _plan_summary(plan)
    d["weeks_json"] = plan.weeks_json or []
    return d


async def create_plan(
    db: AsyncSession, *,
    school_id: str,
    subject_code: str,
    grade_id: str | None,
    semester: str,
    weeks_json: list,
    created_by: str,
) -> dict:
    """Create a teaching plan. Raises ConflictError on duplicate scope."""
    _validate_weeks_json(weeks_json)

    plan = TeachingPlan(
        school_id=school_id,
        subject_code=subject_code,
        grade_id=grade_id,
        semester=semester,
        weeks_json=weeks_json,
        created_by=created_by,
    )
    db.add(plan)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictError("该学校+科目+年级+学期的教学计划已存在")
    await db.refresh(plan)
    logger.info("teaching_plan created: id=%s school=%s subject=%s semester=%s",
                plan.id, school_id, subject_code, semester)
    return _plan_summary(plan)


async def list_plans(
    db: AsyncSession, *,
    school_id: str,
    semester: str | None = None,
    subject_code: str | None = None,
    grade_id: str | None = None,
) -> list[dict]:
    """List teaching plans with optional filters."""
    stmt = select(TeachingPlan).where(TeachingPlan.school_id == school_id)
    if semester:
        stmt = stmt.where(TeachingPlan.semester == semester)
    if subject_code:
        stmt = stmt.where(TeachingPlan.subject_code == subject_code)
    if grade_id:
        stmt = stmt.where(TeachingPlan.grade_id == grade_id)
    stmt = stmt.order_by(TeachingPlan.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [_plan_summary(p) for p in rows]


async def get_plan(
    db: AsyncSession, *,
    plan_id: str,
    school_id: str,
) -> dict:
    """Get a single teaching plan with full weeks_json. Raises NotFoundError."""
    plan = await db.get(TeachingPlan, plan_id)
    if not plan or plan.school_id != school_id:
        raise NotFoundError("教学计划不存在")
    return _plan_detail(plan)


async def update_plan(
    db: AsyncSession, *,
    plan_id: str,
    school_id: str,
    weeks_json: list | None = None,
    subject_code: str | None = None,
) -> dict:
    """Partial update a teaching plan."""
    plan = await db.get(TeachingPlan, plan_id)
    if not plan or plan.school_id != school_id:
        raise NotFoundError("教学计划不存在")

    if weeks_json is not None:
        _validate_weeks_json(weeks_json)
        plan.weeks_json = weeks_json
    if subject_code is not None:
        plan.subject_code = subject_code

    await db.commit()
    await db.refresh(plan)
    logger.info("teaching_plan updated: id=%s", plan_id)
    return _plan_summary(plan)


async def delete_plan(
    db: AsyncSession, *,
    plan_id: str,
    school_id: str,
) -> None:
    """Delete a teaching plan. Raises NotFoundError."""
    plan = await db.get(TeachingPlan, plan_id)
    if not plan or plan.school_id != school_id:
        raise NotFoundError("教学计划不存在")
    await db.delete(plan)
    await db.commit()
    logger.info("teaching_plan deleted: id=%s", plan_id)
