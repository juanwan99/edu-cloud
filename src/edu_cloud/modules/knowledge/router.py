"""知识点路由 — 从 exam-ai 迁入。"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user
from edu_cloud.modules.knowledge import service as knowledge_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


def _kp_response(node) -> dict:
    return {
        "id": node.id,
        "name": node.name,
        "node_type": node.node_type,
        "primary_module": node.primary_module,
        "description": node.description,
        "course_code": node.course_code,
    }


@router.get("/points")
async def list_knowledge_points(
    course_code: str,
    parent_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    kps = await knowledge_service.list_knowledge_points(
        db, course_code=course_code, parent_id=parent_id,
    )
    return [_kp_response(kp) for kp in kps]


@router.get("/points/{kp_id}")
async def get_knowledge_point(
    kp_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    kp = await knowledge_service.get_knowledge_point(db, kp_id=kp_id)
    if kp is None:
        raise HTTPException(status_code=404, detail="Knowledge point not found")
    return _kp_response(kp)


@router.get("/points/{kp_id}/children")
async def get_children(
    kp_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    children = await knowledge_service.get_children(db, parent_id=kp_id)
    return [_kp_response(c) for c in children]


class LinkRequest(BaseModel):
    question_id: str
    concept_id: str
    is_primary: bool = True


@router.post("/link")
async def link_question_to_kp(
    req: LinkRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    link = await knowledge_service.link_question(
        db, question_id=req.question_id,
        concept_id=req.concept_id, is_primary=req.is_primary,
    )
    await db.commit()
    return {"id": link.id, "question_id": link.question_id,
            "concept_id": link.concept_id}


@router.get("/question/{question_id}")
async def get_question_kps(
    question_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    kps = await knowledge_service.get_question_knowledge_points(db, question_id=question_id)
    return [_kp_response(kp) for kp in kps]
