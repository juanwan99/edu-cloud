import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.core.auth import require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.database import get_db
from edu_cloud.services.teacher_assignment_service import (
    list_assignments, create_assignments, delete_assignment, get_summary,
)
from edu_cloud.services.exceptions import NotFoundError, PermissionDeniedError
from edu_cloud.core.tenant import CROSS_SCHOOL_ROLES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/schools/{school_id}", tags=["teacher-assignments"])


def _check_school_scope(current: dict, school_id: str):
    role = current["current_role"]
    if role.role in CROSS_SCHOOL_ROLES:
        return
    if role.school_id != school_id:
        raise PermissionDeniedError("无权访问其他学校的排课数据")


class CreateAssignmentsRequest(BaseModel):
    user_id: str
    class_ids: list[str] = Field(min_length=1)  # P6 fix: reject empty
    subject_code: str
    semester: str


@router.get("/assignments")
async def api_list_assignments(
    school_id: str,
    semester: str | None = None,
    user_id: str | None = None,
    class_id: str | None = None,
    subject_code: str | None = None,
    current=Depends(require_permission(Permission.MANAGE_SCHEDULING)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    rows = await list_assignments(
        db, school_id=school_id, semester=semester,
        user_id=user_id, class_id=class_id, subject_code=subject_code,
    )
    return [
        {"id": r.id, "user_id": r.user_id, "class_id": r.class_id,
         "subject_code": r.subject_code, "semester": r.semester, "is_active": r.is_active}
        for r in rows
    ]


@router.post("/assignments")
async def api_create_assignments(
    school_id: str,
    body: CreateAssignmentsRequest,
    current=Depends(require_permission(Permission.MANAGE_SCHEDULING)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    count = await create_assignments(
        db, school_id=school_id, user_id=body.user_id,
        class_ids=body.class_ids, subject_code=body.subject_code, semester=body.semester,
    )
    return {"created": count}


@router.delete("/assignments/{assignment_id}")
async def api_delete_assignment(
    school_id: str,
    assignment_id: str,
    current=Depends(require_permission(Permission.MANAGE_SCHEDULING)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    await delete_assignment(db, school_id=school_id, assignment_id=assignment_id)
    return {"ok": True}


@router.get("/assignments/summary")
async def api_assignment_summary(
    school_id: str,
    semester: str | None = None,
    current=Depends(require_permission(Permission.MANAGE_SCHEDULING)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    return await get_summary(db, school_id=school_id, semester=semester)
