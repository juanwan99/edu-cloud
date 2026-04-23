"""Dashboard Summary API — 角色 scope 内的聚合统计。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user
from edu_cloud.api.permissions import get_visible_class_ids

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/summary")
async def get_summary(
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    role = current["current_role"]
    school_id = role.school_id
    visible_classes = get_visible_class_ids(role)

    # Import models
    from edu_cloud.models.student import Student
    from edu_cloud.models.class_group import ClassGroup
    from edu_cloud.models.exam import Exam

    # Students count
    q = select(func.count(Student.id))
    if school_id:
        q = q.where(Student.school_id == school_id)
    if visible_classes is not None:
        q = q.where(Student.class_id.in_(visible_classes))
    total_students = (await db.execute(q)).scalar() or 0

    # Classes count
    q = select(func.count(ClassGroup.id))
    if school_id:
        q = q.where(ClassGroup.school_id == school_id)
    if visible_classes is not None:
        q = q.where(ClassGroup.id.in_(visible_classes))
    total_classes = (await db.execute(q)).scalar() or 0

    # Exams count
    q = select(func.count(Exam.id))
    if school_id:
        q = q.where(Exam.school_id == school_id)
    total_exams = (await db.execute(q)).scalar() or 0

    return {
        "total_students": total_students,
        "total_classes": total_classes,
        "total_exams": total_exams,
        "total_staff": None,
        "pending_subjects": None,
        "pending_grading": 0,
    }
