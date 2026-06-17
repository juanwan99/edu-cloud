"""数据流水线路由 — 从 exam-ai 迁入。"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.core.auth import get_current_user
from edu_cloud.api.permissions import is_school_admin
from edu_cloud.services.post_exam_pipeline import run_post_exam_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])


@router.post("/run/{exam_id}")
async def trigger_pipeline(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """手动触发考试数据流水线（题库入库+错题收集+画像更新）。"""
    role = current["current_role"]
    if not is_school_admin(role):
        raise HTTPException(403, "仅管理员和校长可触发数据流水线")

    results = await run_post_exam_pipeline(db, exam_id=exam_id, school_id=role.school_id)
    logger.info("pipeline triggered: exam=%s, by=%s", exam_id, current["user"].username)
    return results
