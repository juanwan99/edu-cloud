"""Admin API routes for conduct management (config + points + rules + groups + semesters + export)."""
import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.modules.conduct.schemas import (
    ConductConfigUpdate, AddPointsRequest,
    RuleCategoryCreate, RuleItemCreate,
    GroupCreate, GroupMemberAdd,
)
from edu_cloud.modules.conduct import admin_service, rules_service, export_service, scope_service
from edu_cloud.api.permissions import get_visible_class_ids
from edu_cloud.modules.conduct.permissions import (
    check_class_scope,
    check_resource_class,
    check_rule_item_class,
    check_students_class,
)
from edu_cloud.models.school import School
from edu_cloud.modules.conduct.models import (
    ConductRuleCategory, ConductRuleItem, ConductGroup, ConductSemester, ConductRecord,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/conduct", tags=["conduct-admin"])


# ═══════════════════════════════════════════════════
# Overview (Scope-Adaptive aggregation)
# ═══════════════════════════════════════════════════

@router.get("/overview")
async def get_overview(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.VIEW_CONDUCT)),
):
    """Return conduct overview data at the appropriate scope for the current user's role.

    Auto-dispatches to class/school/district scope based on active_role.
    Parents must use the parent-specific endpoints, not the admin overview.
    """
    role = current_user["current_role"]

    # F-001: Parents have VIEW_CONDUCT but must not access admin overview
    if role.role == "parent":
        raise HTTPException(status_code=403, detail="家长请使用家长端接口")

    if role.role in ("platform_admin", "district_admin"):
        # District scope: use role's school district or "default"
        if role.school_id:
            school = await db.get(School, role.school_id)
            district = school.district if school and school.district else "default"
        else:
            district = "default"
        return await scope_service.get_conduct_overview(db, "district", [district])

    if role.role in ("principal", "academic_director"):
        # School scope
        if not role.school_id:
            raise HTTPException(400, "Role has no school_id")
        return await scope_service.get_conduct_overview(db, "school", [role.school_id])

    # Other roles: check for class_ids
    visible = get_visible_class_ids(role)
    if visible:
        return await scope_service.get_conduct_overview(db, "class", visible)

    # School-scoped role without class_ids
    if role.school_id:
        return await scope_service.get_conduct_overview(db, "school", [role.school_id])

    raise HTTPException(400, "Cannot determine scope for overview")


# ═══════════════════════════════════════════════════
# Config management (Task 6)
# ═══════════════════════════════════════════════════

@router.get("/classes/{class_id}/config")
async def get_config(
    class_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.MANAGE_CONDUCT_PARENTS)),
):
    """Get conduct config for a class."""
    check_class_scope(current_user, class_id)
    return await admin_service.get_config(db, class_id)


@router.put("/classes/{class_id}/config")
async def update_config(
    class_id: str,
    data: ConductConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.MANAGE_CONDUCT_PARENTS)),
):
    """Update conduct config for a class."""
    check_class_scope(current_user, class_id)
    return await admin_service.update_config(db, class_id, data.model_dump(exclude_none=True))


@router.post("/classes/{class_id}/config/regenerate-code")
async def regenerate_code(
    class_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.MANAGE_CONDUCT_PARENTS)),
):
    """Regenerate invite code for a class."""
    check_class_scope(current_user, class_id)
    return await admin_service.regenerate_invite_code(db, class_id)


@router.get("/classes/{class_id}/parents")
async def list_parents(
    class_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.MANAGE_CONDUCT_PARENTS)),
):
    """List parents bound to students in a class."""
    check_class_scope(current_user, class_id)
    return await admin_service.list_parents(db, class_id)


@router.delete("/classes/{class_id}/parents/{user_id}")
async def remove_parent(
    class_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.MANAGE_CONDUCT_PARENTS)),
):
    """Remove a parent's binding to students in a class."""
    check_class_scope(current_user, class_id)
    return await admin_service.remove_parent(db, class_id, user_id)


# ═══════════════════════════════════════════════════
# Points CRUD (Task 10)
# ═══════════════════════════════════════════════════

@router.post("/classes/{class_id}/records")
async def add_points(
    class_id: str,
    data: AddPointsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.MANAGE_CONDUCT)),
):
    """Add points to one or more students."""
    check_class_scope(current_user, class_id)
    await check_students_class(db, data.student_ids, class_id)
    if data.rule_item_id is not None:
        await check_rule_item_class(db, data.rule_item_id, class_id)
    operator_id = current_user["user"].id
    ids = await admin_service.add_points(
        db, class_id, operator_id,
        data.student_ids, data.points, data.reason,
        rule_item_id=data.rule_item_id,
        record_date=data.record_date,
    )
    return {"created_ids": ids}


@router.post("/classes/{class_id}/records/batch")
async def add_points_batch(
    class_id: str,
    data: AddPointsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.MANAGE_CONDUCT)),
):
    """Batch add points (same as /records, exposed as /batch alias)."""
    check_class_scope(current_user, class_id)
    await check_students_class(db, data.student_ids, class_id)
    if data.rule_item_id is not None:
        await check_rule_item_class(db, data.rule_item_id, class_id)
    operator_id = current_user["user"].id
    ids = await admin_service.add_points(
        db, class_id, operator_id,
        data.student_ids, data.points, data.reason,
        rule_item_id=data.rule_item_id,
        record_date=data.record_date,
    )
    return {"created_ids": ids}


@router.get("/classes/{class_id}/records")
async def get_records(
    class_id: str,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    student_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.VIEW_CONDUCT)),
):
    """Get paginated conduct records for a class."""
    check_class_scope(current_user, class_id)
    return await admin_service.get_records(
        db, class_id, page=page, size=size,
        student_id=student_id, start_date=start_date, end_date=end_date,
    )


@router.delete("/classes/{class_id}/records/{record_id}")
async def delete_record(
    class_id: str,
    record_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.MANAGE_CONDUCT)),
):
    """Delete a conduct record."""
    check_class_scope(current_user, class_id)
    await check_resource_class(db, ConductRecord, record_id, class_id)
    return await admin_service.delete_record(db, class_id, record_id)


@router.get("/classes/{class_id}/rankings/students")
async def get_student_rankings(
    class_id: str,
    semester_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.VIEW_CONDUCT)),
):
    """Get student rankings by total points."""
    check_class_scope(current_user, class_id)
    return await admin_service.get_student_rankings(db, class_id, semester_id=semester_id)


@router.get("/classes/{class_id}/rankings/groups")
async def get_group_rankings(
    class_id: str,
    semester_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.VIEW_CONDUCT)),
):
    """Get group rankings by total member points."""
    check_class_scope(current_user, class_id)
    return await admin_service.get_group_rankings(db, class_id, semester_id=semester_id)


# ═══════════════════════════════════════════════════
# Rules CRUD (Task 11)
# ═══════════════════════════════════════════════════

@router.get("/classes/{class_id}/rules")
async def get_rules(
    class_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.VIEW_CONDUCT)),
):
    """Get nested rule categories + items for a class."""
    check_class_scope(current_user, class_id)
    return await rules_service.get_rules(db, class_id)


@router.post("/classes/{class_id}/rules/categories")
async def create_rule_category(
    class_id: str,
    data: RuleCategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.MANAGE_CONDUCT_RULES)),
):
    """Create a rule category."""
    check_class_scope(current_user, class_id)
    return await rules_service.create_category(
        db, class_id=class_id, name=data.name, scope="class", sort_order=data.sort_order,
    )


@router.put("/classes/{class_id}/rules/categories/{cat_id}")
async def update_rule_category(
    class_id: str,
    cat_id: str,
    data: RuleCategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.MANAGE_CONDUCT_RULES)),
):
    """Update a rule category."""
    check_class_scope(current_user, class_id)
    await check_resource_class(db, ConductRuleCategory, cat_id, class_id)
    return await rules_service.update_category(db, cat_id, name=data.name, sort_order=data.sort_order)


@router.delete("/classes/{class_id}/rules/categories/{cat_id}")
async def delete_rule_category(
    class_id: str,
    cat_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.MANAGE_CONDUCT_RULES)),
):
    """Delete a rule category and all its items."""
    check_class_scope(current_user, class_id)
    await check_resource_class(db, ConductRuleCategory, cat_id, class_id)
    return await rules_service.delete_category(db, cat_id)


@router.post("/classes/{class_id}/rules/categories/{cat_id}/items")
async def create_rule_item(
    class_id: str,
    cat_id: str,
    data: RuleItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.MANAGE_CONDUCT_RULES)),
):
    """Create a rule item under a category."""
    check_class_scope(current_user, class_id)
    await check_resource_class(db, ConductRuleCategory, cat_id, class_id)
    return await rules_service.create_item(db, cat_id, data.name, data.points)


@router.put("/classes/{class_id}/rules/categories/{cat_id}/items/{item_id}")
async def update_rule_item(
    class_id: str,
    cat_id: str,
    item_id: str,
    data: RuleItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.MANAGE_CONDUCT_RULES)),
):
    """Update a rule item."""
    check_class_scope(current_user, class_id)
    await check_resource_class(db, ConductRuleCategory, cat_id, class_id)
    await check_resource_class(db, ConductRuleItem, item_id, cat_id, class_id_path="category_id")
    return await rules_service.update_item(db, item_id, name=data.name, points=data.points)


@router.delete("/classes/{class_id}/rules/categories/{cat_id}/items/{item_id}")
async def delete_rule_item(
    class_id: str,
    cat_id: str,
    item_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.MANAGE_CONDUCT_RULES)),
):
    """Delete a rule item."""
    check_class_scope(current_user, class_id)
    await check_resource_class(db, ConductRuleCategory, cat_id, class_id)
    await check_resource_class(db, ConductRuleItem, item_id, cat_id, class_id_path="category_id")
    return await rules_service.delete_item(db, item_id)


# ═══════════════════════════════════════════════════
# School-level Rules (Task 2 — Cascade)
# ═══════════════════════════════════════════════════

@router.get("/schools/{school_id}/rules")
async def get_school_rules(
    school_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.MANAGE_CONDUCT_RULES)),
):
    """List school-level rule categories with nested items."""
    # F-003: Validate school scope
    role = current_user["current_role"]
    if role.school_id and role.school_id != school_id:
        raise HTTPException(status_code=403, detail="无权访问该学校规则")
    categories = (
        await db.execute(
            select(ConductRuleCategory)
            .where(
                ConductRuleCategory.school_id == school_id,
                ConductRuleCategory.scope == "school",
            )
            .order_by(ConductRuleCategory.sort_order, ConductRuleCategory.name)
        )
    ).scalars().all()

    result = []
    for cat in categories:
        items = (
            await db.execute(
                select(ConductRuleItem)
                .where(ConductRuleItem.category_id == cat.id)
                .order_by(ConductRuleItem.sort_order, ConductRuleItem.name)
            )
        ).scalars().all()
        result.append({
            "id": cat.id,
            "name": cat.name,
            "scope": cat.scope,
            "sort_order": cat.sort_order,
            "items": [
                {
                    "id": item.id,
                    "name": item.name,
                    "points": item.points,
                    "sort_order": item.sort_order,
                }
                for item in items
            ],
        })
    return result


@router.post("/schools/{school_id}/rules/categories")
async def create_school_rule_category(
    school_id: str,
    data: RuleCategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.MANAGE_CONDUCT_RULES)),
):
    """Create a school-level rule category."""
    # F-003: Validate school scope
    role = current_user["current_role"]
    if role.school_id and role.school_id != school_id:
        raise HTTPException(status_code=403, detail="无权访问该学校规则")
    return await rules_service.create_category(
        db, school_id=school_id, name=data.name, scope="school", sort_order=data.sort_order,
    )


# ═══════════════════════════════════════════════════
# Groups (Task 12)
# ═══════════════════════════════════════════════════

@router.get("/classes/{class_id}/groups")
async def get_groups(
    class_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.VIEW_CONDUCT)),
):
    """List groups with members."""
    check_class_scope(current_user, class_id)
    return await admin_service.get_groups(db, class_id)


@router.post("/classes/{class_id}/groups")
async def create_group(
    class_id: str,
    data: GroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.MANAGE_CONDUCT)),
):
    """Create a group."""
    check_class_scope(current_user, class_id)
    return await admin_service.create_group(db, class_id, data.name, avatar=data.avatar)


@router.delete("/classes/{class_id}/groups/{group_id}")
async def delete_group(
    class_id: str,
    group_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.MANAGE_CONDUCT)),
):
    """Delete a group and its members."""
    check_class_scope(current_user, class_id)
    await check_resource_class(db, ConductGroup, group_id, class_id)
    return await admin_service.delete_group(db, group_id)


@router.post("/classes/{class_id}/groups/{group_id}/members")
async def add_group_members(
    class_id: str,
    group_id: str,
    data: GroupMemberAdd,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.MANAGE_CONDUCT)),
):
    """Add students to a group."""
    check_class_scope(current_user, class_id)
    await check_resource_class(db, ConductGroup, group_id, class_id)
    await check_students_class(db, data.student_ids, class_id)
    return await admin_service.add_group_members(db, group_id, data.student_ids)


@router.delete("/classes/{class_id}/groups/{group_id}/members/{student_id}")
async def remove_group_member(
    class_id: str,
    group_id: str,
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.MANAGE_CONDUCT)),
):
    """Remove a student from a group."""
    check_class_scope(current_user, class_id)
    await check_resource_class(db, ConductGroup, group_id, class_id)
    await check_students_class(db, [student_id], class_id)
    return await admin_service.remove_group_member(db, group_id, student_id)


# ═══════════════════════════════════════════════════
# Semesters (Task 12)
# ═══════════════════════════════════════════════════

@router.get("/classes/{class_id}/semesters")
async def get_semesters(
    class_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.VIEW_CONDUCT)),
):
    """List semesters for a class."""
    check_class_scope(current_user, class_id)
    return await admin_service.get_semesters(db, class_id)


@router.post("/classes/{class_id}/semesters")
async def create_semester(
    class_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.MANAGE_CONDUCT_RULES)),
):
    """Create a semester for a class."""
    check_class_scope(current_user, class_id)
    return await admin_service.create_semester(
        db, class_id,
        name=data["name"],
        start_date=date.fromisoformat(data["start_date"]),
        end_date=date.fromisoformat(data["end_date"]),
    )


@router.put("/classes/{class_id}/semesters/{semester_id}/activate")
async def activate_semester(
    class_id: str,
    semester_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.MANAGE_CONDUCT_RULES)),
):
    """Activate a semester (deactivates others in the same class)."""
    check_class_scope(current_user, class_id)
    await check_resource_class(db, ConductSemester, semester_id, class_id)
    return await admin_service.activate_semester(db, semester_id)


# ═══════════════════════════════════════════════════
# Reports (P2-T1)
# ═══════════════════════════════════════════════════

@router.get("/classes/{class_id}/report")
async def get_class_report(
    class_id: str,
    semester_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.VIEW_CONDUCT)),
):
    """Generate a semester conduct evaluation report for a class."""
    check_class_scope(current_user, class_id)
    from edu_cloud.modules.conduct.report_service import generate_semester_report
    return await generate_semester_report(db, class_id, semester_id)


@router.get("/schools/{school_id}/report")
async def get_school_report(
    school_id: str,
    semester_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.VIEW_CONDUCT)),
):
    """Generate a school-wide semester conduct evaluation report."""
    # F-002: Validate school scope — users bound to a school can only access their own
    role = current_user["current_role"]
    if role.school_id and role.school_id != school_id:
        raise HTTPException(status_code=403, detail="无权访问该学校数据")
    from edu_cloud.modules.conduct.report_service import generate_school_report
    return await generate_school_report(db, school_id, semester_id)


# ═══════════════════════════════════════════════════
# Export (Task 16)
# ═══════════════════════════════════════════════════

@router.get("/classes/{class_id}/export/records")
async def export_records(
    class_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.EXPORT_CONDUCT)),
):
    """Export conduct records as Excel file."""
    check_class_scope(current_user, class_id)
    sd = date.fromisoformat(start_date) if start_date else None
    ed = date.fromisoformat(end_date) if end_date else None
    buf = await export_service.export_records_excel(db, class_id, sd, ed)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=conduct_records.xlsx"},
    )


@router.get("/classes/{class_id}/export/rankings")
async def export_rankings(
    class_id: str,
    semester_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(Permission.EXPORT_CONDUCT)),
):
    """Export conduct rankings as Excel file."""
    check_class_scope(current_user, class_id)
    buf = await export_service.export_rankings_excel(db, class_id, semester_id)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=conduct_rankings.xlsx"},
    )
