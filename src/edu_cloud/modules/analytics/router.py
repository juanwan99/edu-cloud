"""统计分析路由 — 从 exam-ai 迁入。支持 subject_id 单参数查询（Phase 2.3 examids 统一）。"""
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user
from edu_cloud.api.permissions import get_visible_subject_codes, get_visible_class_ids
from edu_cloud.modules.analytics import service as analytics_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


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
