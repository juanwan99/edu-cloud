"""统计分析路由 — 从 exam-ai 迁入。支持 subject_id 单参数查询（Phase 2.3 examids 统一）。"""
import logging
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.core.auth import get_current_user, require_permission
from edu_cloud.api.permissions import get_visible_subject_codes, get_visible_class_ids
from edu_cloud.core.permissions import Permission
from edu_cloud.modules.analytics import service as analytics_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

# --- 子路由注册 ---
from edu_cloud.modules.analytics.analytics_report_router import router as report_sub_router
router.include_router(report_sub_router)


@router.get("/exam/{exam_id}/summary")
async def exam_summary(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    role = current["current_role"]
    return await analytics_service.exam_summary(
        db, exam_id=exam_id, school_id=role.school_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


@router.get("/subject/{subject_id}/summary")
async def subject_summary(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """单科目维度的考试总览。通过 subject_id 自动解析 exam_id。"""
    role = current["current_role"]
    exam_id, _ = await analytics_service.resolve_subject_to_exam(
        db, subject_id, role.school_id,
    )
    return await analytics_service.exam_summary(
        db, exam_id=exam_id, school_id=role.school_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


@router.get("/exam/{exam_id}/distribution")
async def exam_distribution(
    exam_id: str,
    subject_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    role = current["current_role"]
    return await analytics_service.exam_distribution(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


@router.get("/subject/{subject_id}/distribution")
async def subject_distribution(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """单科目维度的成绩分布。通过 subject_id 自动解析 exam_id。"""
    role = current["current_role"]
    exam_id, _ = await analytics_service.resolve_subject_to_exam(
        db, subject_id, role.school_id,
    )
    return await analytics_service.exam_distribution(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


@router.get("/subject/{subject_id}/questions")
async def subject_question_analysis(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    role = current["current_role"]
    return await analytics_service.subject_question_analysis(
        db, subject_id=subject_id, school_id=role.school_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


@router.get("/exam/{exam_id}/grade-aggregates")
async def grade_aggregates(
    exam_id: str,
    subject_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    role = current["current_role"]
    return await analytics_service.grade_aggregates(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


@router.get("/subject/{subject_id}/grade-aggregates")
async def subject_grade_aggregates(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """单科目维度的年级聚合统计。通过 subject_id 自动解析 exam_id。"""
    role = current["current_role"]
    exam_id, _ = await analytics_service.resolve_subject_to_exam(
        db, subject_id, role.school_id,
    )
    return await analytics_service.grade_aggregates(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


# --- 分数段配置管理 ---

from edu_cloud.modules.analytics.segment_service import (
    get_segment_config, upsert_segment_config, list_segment_configs,
)


@router.get("/segments/config")
async def get_segments_config(
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_EXAM_RESULTS)),
):
    """获取本校分数段配置（默认 + 科目覆盖列表）。"""
    role = current["current_role"]
    school_id = role.school_id
    configs = await list_segment_configs(db, school_id)
    default_cfg = next((c for c in configs if c.subject_code is None), None)
    overrides = [c for c in configs if c.subject_code is not None]
    return {
        "default": {
            "boundaries": default_cfg.boundaries if default_cfg else [85, 70, 60],
            "labels": default_cfg.labels if default_cfg else ["优秀", "良好", "及格", "不及格"],
        },
        "overrides": [
            {"subject_code": c.subject_code, "boundaries": c.boundaries, "labels": c.labels}
            for c in overrides
        ],
    }


@router.put("/segments/config")
async def update_segments_config(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_EXAM_RESULTS)),
):
    """创建或更新分数段配置（upsert）。"""
    role = current["current_role"]
    user = current["user"]
    cfg = await upsert_segment_config(
        db,
        school_id=role.school_id,
        boundaries=body["boundaries"],
        labels=body["labels"],
        created_by=user.id,
        subject_code=body.get("subject_code"),
    )
    await db.commit()
    return {
        "subject_code": cfg.subject_code,
        "boundaries": cfg.boundaries,
        "labels": cfg.labels,
    }


@router.delete("/segments/config/{subject_code}")
async def delete_segment_override(
    subject_code: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_EXAM_RESULTS)),
):
    """删除科目覆盖配置（硬删）。不允许删除学校默认。"""
    role = current["current_role"]
    from sqlalchemy import select as sa_select, delete as sa_delete
    from edu_cloud.models.score_segment import ScoreSegmentConfig as SSC
    result = await db.execute(
        sa_select(SSC).where(
            SSC.school_id == role.school_id,
            SSC.subject_code == subject_code,
        )
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(404, "配置不存在")
    await db.execute(
        sa_delete(SSC).where(SSC.id == cfg.id)
    )
    await db.commit()
    return {"deleted": subject_code}


