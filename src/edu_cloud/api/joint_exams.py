"""联考管理 REST 端点。"""
import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.services.joint_exam_service import JointExamService
from edu_cloud.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/joint-exams", tags=["joint-exams"])


class CreateExamRequest(BaseModel):
    name: str
    subjects: list[dict]
    creator_school_id: str
    description: str | None = None


class AddParticipantRequest(BaseModel):
    school_id: str


@router.post("", status_code=201)
async def create_exam(
    req: CreateExamRequest,
    user=Depends(require_permission(Permission.CREATE_JOINT_EXAM)),
    db: AsyncSession = Depends(get_db),
):
    svc = JointExamService(db, upload_dir=settings.UPLOAD_DIR)
    exam = await svc.create_exam(
        name=req.name,
        subjects=req.subjects,
        creator_school_id=req.creator_school_id,
        created_by=user.id,
        description=req.description,
    )
    logger.info("joint exam created via API: id=%s by user=%s", exam.id, user.username)
    return {
        "id": exam.id, "name": exam.name, "status": exam.status,
        "subjects": exam.subjects, "creator_school_id": exam.creator_school_id,
    }


@router.get("")
async def list_exams(
    status: str | None = None,
    user=Depends(require_permission(Permission.VIEW_JOINT_EXAM)),
    db: AsyncSession = Depends(get_db),
):
    svc = JointExamService(db)
    exams = await svc.list_exams(status=status)
    return [
        {"id": e.id, "name": e.name, "status": e.status,
         "subjects": e.subjects, "created_at": str(e.created_at)}
        for e in exams
    ]


@router.get("/{exam_id}")
async def get_exam(
    exam_id: str,
    user=Depends(require_permission(Permission.VIEW_JOINT_EXAM)),
    db: AsyncSession = Depends(get_db),
):
    svc = JointExamService(db)
    return await svc.get_exam_detail(exam_id)


@router.post("/{exam_id}/participants", status_code=201)
async def add_participant(
    exam_id: str,
    req: AddParticipantRequest,
    user=Depends(require_permission(Permission.MANAGE_JOINT_EXAM)),
    db: AsyncSession = Depends(get_db),
):
    svc = JointExamService(db)
    p = await svc.add_participant(exam_id, req.school_id)
    return {"school_id": p.school_id, "status": p.status}


@router.delete("/{exam_id}/participants/{school_id}", status_code=204)
async def remove_participant(
    exam_id: str,
    school_id: str,
    user=Depends(require_permission(Permission.MANAGE_JOINT_EXAM)),
    db: AsyncSession = Depends(get_db),
):
    svc = JointExamService(db)
    await svc.remove_participant(exam_id, school_id)


@router.post("/{exam_id}/distribute")
async def distribute(
    exam_id: str,
    user=Depends(require_permission(Permission.MANAGE_JOINT_EXAM)),
    db: AsyncSession = Depends(get_db),
):
    svc = JointExamService(db, upload_dir=settings.UPLOAD_DIR)
    exam = await svc.distribute(exam_id)
    return {"id": exam.id, "status": exam.status}


@router.post("/{exam_id}/force-complete")
async def force_complete(
    exam_id: str,
    user=Depends(require_permission(Permission.MANAGE_JOINT_EXAM)),
    db: AsyncSession = Depends(get_db),
):
    svc = JointExamService(db)
    exam = await svc.force_complete(exam_id)
    return {"id": exam.id, "status": exam.status}
