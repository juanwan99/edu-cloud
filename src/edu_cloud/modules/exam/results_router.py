"""成绩查看 REST 端点。"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.core.tenant import get_school_id
from edu_cloud.services.results_service import ResultsService

router = APIRouter(prefix="/api/v1/joint-exams/{exam_id}/results", tags=["results"])


@router.get("")
async def get_rankings(
    exam_id: str,
    subject_code: str | None = None,
    current: dict = Depends(require_permission(Permission.VIEW_JOINT_EXAM)),
    db: AsyncSession = Depends(get_db),
):
    svc = ResultsService(db)
    return await svc.get_rankings(exam_id, school_id=get_school_id(current), subject_code=subject_code)


@router.get("/by-school")
async def get_school_comparison(
    exam_id: str,
    current: dict = Depends(require_permission(Permission.VIEW_JOINT_EXAM)),
    db: AsyncSession = Depends(get_db),
):
    svc = ResultsService(db)
    return await svc.get_school_comparison(exam_id, school_id=get_school_id(current))


@router.get("/students/{student_number}")
async def get_student_detail(
    exam_id: str,
    student_number: str,
    current: dict = Depends(require_permission(Permission.VIEW_JOINT_EXAM)),
    db: AsyncSession = Depends(get_db),
):
    svc = ResultsService(db)
    return await svc.get_student_detail(exam_id, student_number, school_id=get_school_id(current))
