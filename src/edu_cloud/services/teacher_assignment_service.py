from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.teacher_assignment import TeacherAssignment
from edu_cloud.models.user import User
from edu_cloud.modules.student.models import Class
from edu_cloud.core.scope_filter import ScopeFilter
from edu_cloud.services.audit_service import audited
from edu_cloud.services.exceptions import NotFoundError, ValidationError


async def list_assignments(
    db: AsyncSession, *, school_id: str,
    semester: str | None = None, user_id: str | None = None,
    class_id: str | None = None, subject_code: str | None = None,
    scope: ScopeFilter | None = None,
) -> list[TeacherAssignment]:
    stmt = select(TeacherAssignment).where(TeacherAssignment.school_id == school_id)
    if semester:
        stmt = stmt.where(TeacherAssignment.semester == semester)
    if user_id:
        stmt = stmt.where(TeacherAssignment.user_id == user_id)
    if class_id:
        stmt = stmt.where(TeacherAssignment.class_id == class_id)
    if subject_code:
        stmt = stmt.where(TeacherAssignment.subject_code == subject_code)
    if scope:
        stmt = scope.apply(stmt, TeacherAssignment, class_col="class_id", subject_col="subject_code")
    result = await db.execute(stmt.order_by(TeacherAssignment.created_at))
    return list(result.scalars().all())


@audited("teacher_assignment", action="create")
async def create_assignments(
    db: AsyncSession, *, school_id: str, user_id: str,
    class_ids: list[str], subject_code: str, semester: str,
) -> int:
    """Batch create assignments. Skips existing (idempotent). Returns count created."""
    # P2 fix: validate class_ids belong to target school
    if class_ids:
        rows = (await db.execute(
            select(Class.id, Class.school_id).where(Class.id.in_(class_ids))
        )).all()
        found_ids = {r[0] for r in rows}
        missing = set(class_ids) - found_ids
        if missing:
            raise ValidationError(f"班级 ID 不存在: {missing}")
        wrong_school = {r[0] for r in rows if r[1] != school_id}
        if wrong_school:
            raise ValidationError(f"班级不属于目标学校: {wrong_school}")

    created = 0
    for cid in class_ids:
        existing = (await db.execute(
            select(TeacherAssignment).where(
                TeacherAssignment.user_id == user_id,
                TeacherAssignment.class_id == cid,
                TeacherAssignment.subject_code == subject_code,
                TeacherAssignment.semester == semester,
            )
        )).scalar_one_or_none()
        if not existing:
            db.add(TeacherAssignment(
                user_id=user_id, class_id=cid, subject_code=subject_code,
                semester=semester, school_id=school_id,
            ))
            created += 1
    await db.commit()
    return created


@audited("teacher_assignment", action="delete", id_param="assignment_id")
async def delete_assignment(
    db: AsyncSession, *, school_id: str, assignment_id: str,
) -> None:
    row = (await db.execute(
        select(TeacherAssignment).where(
            TeacherAssignment.id == assignment_id,
            TeacherAssignment.school_id == school_id,
        )
    )).scalar_one_or_none()
    if not row:
        raise NotFoundError("排课记录不存在")
    await db.delete(row)
    await db.commit()


async def get_summary(
    db: AsyncSession, *, school_id: str, semester: str | None = None,
) -> list[dict]:
    """Per-teacher summary: display_name, class_count, subject_codes."""
    stmt = (
        select(
            TeacherAssignment.user_id,
            func.count(TeacherAssignment.id).label("class_count"),
        )
        .where(TeacherAssignment.school_id == school_id)
        .group_by(TeacherAssignment.user_id)
    )
    if semester:
        stmt = stmt.where(TeacherAssignment.semester == semester)
    rows = (await db.execute(stmt)).all()

    result = []
    for user_id, class_count in rows:
        user = await db.get(User, user_id)
        # Get distinct subject codes
        subj_stmt = (
            select(TeacherAssignment.subject_code)
            .where(TeacherAssignment.school_id == school_id,
                   TeacherAssignment.user_id == user_id)
            .distinct()
        )
        if semester:
            subj_stmt = subj_stmt.where(TeacherAssignment.semester == semester)
        subjects = [r[0] for r in (await db.execute(subj_stmt)).all()]
        result.append({
            "user_id": user_id,
            "display_name": user.display_name if user else "Unknown",
            "class_count": class_count,
            "subject_codes": subjects,
        })
    return result
