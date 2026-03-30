"""阅卷分配 API 路由。"""
import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user, require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.modules.grading.assignment_service import GradingAssignmentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/grading", tags=["grading-assignments"])


class AssignBlockRequest(BaseModel):
    exam_id: str
    subject_id: str
    question_ids: list[str]
    teacher_id: str
    school_id: str | None = None
    total_count: int = 0


def _school_id(current: dict) -> str | None:
    return current["current_role"].school_id


def _assignment_response(a) -> dict:
    return {
        "id": a.id, "exam_id": a.exam_id, "subject_id": a.subject_id,
        "question_ids": a.question_ids, "assigned_to": a.assigned_to,
        "status": a.status, "graded_count": a.graded_count,
        "total_count": a.total_count, "school_id": a.school_id,
    }


@router.post("/assignments", status_code=201)
async def create_assignment(
    req: AssignBlockRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
):
    school_id = req.school_id or _school_id(current)
    result = await GradingAssignmentService.assign_block(
        db, exam_id=req.exam_id, subject_id=req.subject_id,
        question_ids=req.question_ids, teacher_id=req.teacher_id,
        school_id=school_id, total_count=req.total_count,
    )
    return _assignment_response(result)


@router.get("/assignments")
async def list_assignments(
    exam_id: str = Query(...),
    school_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_GRADING)),
):
    sid = school_id or _school_id(current)
    if not sid:
        return []
    result = await GradingAssignmentService.list_assignments(db, exam_id, school_id=sid)
    return [_assignment_response(a) for a in result]


@router.get("/progress/{exam_id}")
async def get_progress(
    exam_id: str,
    school_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_GRADING)),
):
    sid = school_id or _school_id(current) or ""
    return await GradingAssignmentService.get_progress(db, exam_id, school_id=sid)
