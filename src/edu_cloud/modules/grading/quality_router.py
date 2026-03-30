"""质量检查 API 路由。"""
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.modules.grading.quality_service import QualityCheckService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/grading", tags=["grading-quality"])

_CROSS_SCHOOL_ROLES = {"platform_admin", "district_admin"}


def _resolve_school_id(current: dict, requested_school_id: str | None = None) -> str:
    role = current["current_role"]
    if role.role in _CROSS_SCHOOL_ROLES and requested_school_id:
        return requested_school_id
    return role.school_id


@router.get("/quality-report/{exam_id}")
async def get_quality_report(
    exam_id: str,
    school_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_GRADING)),
):
    sid = _resolve_school_id(current, school_id) or ""
    return await QualityCheckService.get_quality_report(db, exam_id, school_id=sid)
