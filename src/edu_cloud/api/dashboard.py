"""Dashboard Summary API — 角色 scope 内的聚合统计。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user
from edu_cloud.api.permissions import get_visible_class_ids, get_visible_subject_codes

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/summary")
async def get_summary(
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    role = current["current_role"]
    school_id = role.school_id
    visible_classes = get_visible_class_ids(role)
    visible_subjects = get_visible_subject_codes(role)

    from edu_cloud.models.student import Student
    from edu_cloud.models.class_group import ClassGroup
    from edu_cloud.models.exam import Exam
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.modules.grading.models import GradingTask

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

    # Staff count (distinct non-parent users with roles in this school)
    total_staff = 0
    if school_id:
        q = select(func.count(distinct(UserRole.user_id))).where(
            UserRole.school_id == school_id,
            UserRole.role != "parent",
        )
        total_staff = (await db.execute(q)).scalar() or 0

    # Pending grading tasks — with subject scope
    pending_grading = 0
    if school_id:
        q = select(func.count(GradingTask.id)).where(
            GradingTask.school_id == school_id,
            GradingTask.status == "pending",
        )
        if visible_subjects is not None:
            from edu_cloud.modules.exam.models import Subject as SubjectModel
            q = q.join(SubjectModel, GradingTask.subject_id == SubjectModel.id)
            if len(visible_subjects) == 0:
                q = q.where(SubjectModel.code.in_([]))  # deny-all
            else:
                q = q.where(SubjectModel.code.in_(visible_subjects))
        pending_grading = (await db.execute(q)).scalar() or 0

    # Pending subjects (distinct subjects with active grading tasks) — with subject scope
    pending_subjects = 0
    if school_id:
        q = select(func.count(distinct(GradingTask.subject_id))).where(
            GradingTask.school_id == school_id,
            GradingTask.status.in_(["pending", "processing"]),
        )
        if visible_subjects is not None:
            from edu_cloud.modules.exam.models import Subject as SubjectModel
            q = q.join(SubjectModel, GradingTask.subject_id == SubjectModel.id)
            if len(visible_subjects) == 0:
                q = q.where(SubjectModel.code.in_([]))  # deny-all
            else:
                q = q.where(SubjectModel.code.in_(visible_subjects))
        pending_subjects = (await db.execute(q)).scalar() or 0

    return {
        "total_students": total_students,
        "total_classes": total_classes,
        "total_exams": total_exams,
        "total_staff": total_staff,
        "pending_subjects": pending_subjects,
        "pending_grading": pending_grading,
    }
