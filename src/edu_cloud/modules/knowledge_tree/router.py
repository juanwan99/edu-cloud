"""知识树 API 端点。"""

import logging
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.api.deps import get_db, get_current_user, require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.modules.knowledge_tree.schemas import (
    GraphResponse, MasteryResponse, EditRequest, EditResponse,
    ExamItemsResponse, StatsOverviewResponse,
)
from edu_cloud.modules.knowledge_tree import service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/knowledge-tree", tags=["knowledge-tree"])


@router.get("/graph", response_model=GraphResponse)
async def get_graph(
    module: str = Query("all", description="模块过滤: M1/M2/M3/M4/M5/all"),
    include_draft: bool = Query(True, description="是否包含未审核内容"),
    db: AsyncSession = Depends(get_db),
    current=Depends(require_permission(Permission.VIEW_KNOWLEDGE_TREE)),
):
    """获取知识图谱结构（节点+边）。"""
    # 角色强制覆盖：学生/家长在非宽限期强制 include_draft=false
    role = current["current_role"].role
    if role in ("parent", "student"):
        from edu_cloud.config import settings
        if not settings.KNOWLEDGE_DRAFT_VISIBLE:
            include_draft = False
    return await service.get_graph(db, module=module, include_draft=include_draft)


@router.get("/mastery", response_model=MasteryResponse)
async def get_mastery(
    student_id: str | None = Query(None, description="学生 ID（家长/学生角色可省略，从上下文推导）"),
    module: str = Query("all", description="模块过滤"),
    db: AsyncSession = Depends(get_db),
    current=Depends(require_permission(Permission.VIEW_KNOWLEDGE_TREE)),
):
    """获取学生掌握度数据（聚合到概念和模块级别）。"""
    school_id = current["current_role"].school_id
    # 未传 student_id 时返回空掌握度（图谱结构仍可通过 /graph 获取）
    if not student_id:
        return {"student_id": "", "concept_mastery": [], "module_mastery": []}
    return await service.get_mastery(db, student_id=student_id, module=module, school_id=school_id)


@router.get("/graph/{node_id}/detail")
async def get_node_detail_endpoint(
    node_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_KNOWLEDGE_TREE)),
):
    """获取概念节点详情（课标/教材/DA/真题）。"""
    from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode
    node = (await db.execute(select(ConceptGraphNode).where(ConceptGraphNode.id == node_id))).scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    pg_node = {"id": node.id, "name": node.name, "level": node.knowledge_level,
               "module": node.primary_module, "description": node.description}
    from edu_cloud.modules.knowledge_tree.detail_service import get_node_detail
    return get_node_detail(node_id, pg_node=pg_node)


@router.get("/search")
async def search_concepts(
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_user),
):
    """搜索知识点（name + aliases + description）。"""
    return await service.search_concepts(db, q)


@router.get("/quality-check")
async def quality_check(
    module: str = Query("all", description="模块过滤"),
    db: AsyncSession = Depends(get_db),
    current=Depends(require_permission(Permission.EDIT_KNOWLEDGE_TREE)),
):
    """知识图谱质量巡检（6 条规则）。"""
    from edu_cloud.modules.knowledge_tree.quality_service import run_quality_check
    return await run_quality_check(db, module=module)


@router.get("/graph/{node_id}/exam-items", response_model=ExamItemsResponse)
async def get_exam_items_endpoint(
    node_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current=Depends(require_permission(Permission.VIEW_KNOWLEDGE_TREE)),
):
    """概念关联的高考真题列表（分页）。

    knowledge.db 不可达时返回 total=0 空列表（降级，不 500）。
    """
    import os
    from pathlib import Path
    from edu_cloud.modules.knowledge_tree.exam_items_service import get_exam_items

    kb_path = os.environ.get(
        "KNOWLEDGE_DB_PATH",
        str(Path.home() / "edu-knowledge-base" / "knowledge.db"),
    )
    if not Path(kb_path).exists():
        return {"total": 0, "items": [], "page": page, "page_size": page_size}
    return get_exam_items(kb_path, node_id, page, page_size)


@router.get("/stats/overview", response_model=StatsOverviewResponse)
async def get_stats_overview_endpoint(
    module: str = Query("all", description="模块过滤: M1/M2/M3/M4/M5/all"),
    db: AsyncSession = Depends(get_db),
    current=Depends(require_permission(Permission.VIEW_KNOWLEDGE_TREE)),
):
    """知识图谱全模块统计概览（total_concepts/edges + 考频分布 + 模块聚合）。"""
    from edu_cloud.modules.knowledge_tree.exam_items_service import get_stats_overview
    return await get_stats_overview(db, module)


@router.post("/edit", response_model=EditResponse)
async def edit_graph(
    req: EditRequest,
    db: AsyncSession = Depends(get_db),
    current=Depends(require_permission(Permission.EDIT_KNOWLEDGE_TREE)),
):
    """编辑知识图谱（教师/管理员）。"""
    operations = [op.model_dump() for op in req.operations]
    applied = await service.apply_edits(db, operations)
    logger.info("knowledge tree edited: %d operations applied", applied)
    return EditResponse(success=True, applied=applied)
