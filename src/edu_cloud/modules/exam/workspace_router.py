"""工作台 API：左栏上下文 + 考试仪表板。"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import require_permission
from edu_cloud.api.permissions import get_visible_subject_codes
from edu_cloud.core.permissions import Permission
from edu_cloud.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/api/v1/workspace", tags=["workspace"])


@router.get("/context")
async def get_context(
    current: dict = Depends(require_permission(Permission.VIEW_EXAMS)),
    db: AsyncSession = Depends(get_db),
):
    """获取左栏上下文数据（班级 + 近期考试），按角色 scope 过滤。"""
    svc = WorkspaceService(db)
    role = current["current_role"]
    scope = {
        "class_ids": getattr(role, "class_ids", None),
        "grade_ids": getattr(role, "grade_ids", None),
        "subject_codes": get_visible_subject_codes(role),
    }
    school_id = getattr(role, "school_id", None)
    return await svc.get_context_tree(school_id, scope)


@router.get("/exams/{exam_id}/dashboard")
async def get_exam_dashboard(
    exam_id: str,
    current: dict = Depends(require_permission(Permission.VIEW_EXAMS)),
    db: AsyncSession = Depends(get_db),
):
    """获取考试仪表板数据（统计摘要 + 成绩分布）。"""
    svc = WorkspaceService(db)
    role = current["current_role"]
    scope = {
        "class_ids": getattr(role, "class_ids", None),
        "grade_ids": getattr(role, "grade_ids", None),
        "subject_codes": get_visible_subject_codes(role),
    }
    school_id = getattr(role, "school_id", None)
    return await svc.get_exam_dashboard(exam_id, school_id, scope)
