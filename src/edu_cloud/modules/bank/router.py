"""题库 + 错题本 API 路由。"""
import logging

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.core.auth import require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.modules.bank import service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/bank", tags=["bank"])


def _school_id(current: dict) -> str:
    return current["current_role"].school_id


def _bank_question_response(q) -> dict:
    return {
        "id": q.id, "source_question_id": q.source_question_id,
        "source_exam_id": q.source_exam_id,
        "question_type": q.question_type, "max_score": q.max_score,
        "difficulty": q.difficulty, "discrimination": q.discrimination,
        "common_errors": q.common_errors, "sample_count": q.sample_count,
    }


def _search_question_response(q) -> dict:
    """搜索结果序列化 — 包含 S1-A 扩展字段，排除 embedding 大字段。"""
    return {
        "id": q.id,
        "content_text": q.content_text,
        "question_type": q.question_type,
        "max_score": q.max_score,
        "difficulty": q.difficulty,
        "difficulty_level": q.difficulty_level,
        "source": q.source,
        "tags": q.tags,
        "knowledge_point_ids": q.knowledge_point_ids,
        "bloom_level": q.bloom_level,
        "explanation": q.explanation,
        "sample_count": q.sample_count,
        "source_exam_id": q.source_exam_id,
    }


def _error_book_response(e) -> dict:
    return {
        "id": e.id, "student_id": e.student_id, "question_id": e.question_id,
        "exam_id": e.exam_id, "student_score": e.student_score,
        "max_score": e.max_score, "error_type": e.error_type,
        "ai_feedback": e.ai_feedback, "mastery_status": e.mastery_status,
        "retry_count": e.retry_count, "knowledge_point_ids": e.knowledge_point_ids,
        "is_starred": e.is_starred,
    }


async def _check_student_class_access(
    db: AsyncSession, student_id: str, current: dict,
) -> None:
    """L2: verify the student belongs to a class within the caller's visible scope."""
    from edu_cloud.api.permissions import get_visible_class_ids
    from edu_cloud.services.bank_workflow import Student
    from fastapi import HTTPException
    from sqlalchemy import select

    visible = get_visible_class_ids(current["current_role"])
    if visible is None:
        return
    student = (await db.execute(
        select(Student).where(
            Student.id == student_id,
            Student.school_id == _school_id(current),
        )
    )).scalar_one_or_none()
    if not student or (student.class_id not in visible):
        raise HTTPException(403, "No access to this student")


@router.get("/questions/search")
async def search_questions(
    question_type: Optional[str] = Query(None),
    difficulty_level: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    tags: Optional[list[str]] = Query(None),
    knowledge_point_ids: Optional[list[str]] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_QUESTION_BANK)),
):
    """多条件组合搜索题库（分页）。"""
    from edu_cloud.api.permissions import get_visible_subject_codes
    visible_subjects = get_visible_subject_codes(current["current_role"])

    result = await service.search_questions(
        db, school_id=_school_id(current),
        question_type=question_type,
        difficulty_level=difficulty_level,
        source=source,
        tags=tags,
        knowledge_point_ids=knowledge_point_ids,
        keyword=keyword,
        page=page,
        page_size=page_size,
        visible_subject_codes=visible_subjects,
    )
    return {
        "items": [_search_question_response(q) for q in result["items"]],
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
    }


@router.get("/questions/stats/overview")
async def get_questions_stats_overview(
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_QUESTION_BANK)),
):
    """本校题库统计概览。"""
    from edu_cloud.api.permissions import get_visible_subject_codes
    visible_subjects = get_visible_subject_codes(current["current_role"])

    return await service.get_questions_stats_overview(
        db, school_id=_school_id(current),
        visible_subject_codes=visible_subjects,
    )


@router.get("/questions")
async def list_bank_questions(
    question_type: str | None = Query(None),
    min_difficulty: float | None = Query(None),
    max_difficulty: float | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_QUESTION_BANK)),
):
    from edu_cloud.api.permissions import get_visible_subject_codes
    visible_subjects = get_visible_subject_codes(current["current_role"])

    questions = await service.list_bank_questions(
        db, school_id=_school_id(current),
        question_type=question_type,
        min_difficulty=min_difficulty, max_difficulty=max_difficulty,
        limit=limit,
        visible_subject_codes=visible_subjects,
    )
    return [_bank_question_response(q) for q in questions]


@router.get("/questions/{question_id}")
async def get_bank_question(
    question_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_QUESTION_BANK)),
):
    from edu_cloud.api.permissions import get_visible_subject_codes
    visible_subjects = get_visible_subject_codes(current["current_role"])

    q = await service.get_bank_question(
        db, bank_question_id=question_id, school_id=_school_id(current),
        visible_subject_codes=visible_subjects,
    )
    return _bank_question_response(q)


@router.get("/error-book/{student_id}")
async def get_student_error_book(
    student_id: str,
    mastery_status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_SCORES)),
):
    await _check_student_class_access(db, student_id, current)
    items = await service.get_student_error_book(
        db, student_id=student_id, school_id=_school_id(current),
        mastery_status=mastery_status, limit=limit,
    )
    return [_error_book_response(e) for e in items]


@router.get("/error-book/{student_id}/knowledge-summary")
async def get_error_knowledge_summary(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_SCORES)),
):
    """按知识点聚合学生错题，返回薄弱知识点列表。"""
    await _check_student_class_access(db, student_id, current)
    return await service.get_error_knowledge_summary(
        db, student_id=student_id, school_id=_school_id(current),
    )


@router.get("/error-book/{student_id}/recommendations")
async def get_recommended_practice(
    student_id: str,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_SCORES)),
):
    """基于薄弱知识点推荐练习题。"""
    await _check_student_class_access(db, student_id, current)
    return await service.get_recommended_practice(
        db, student_id=student_id, school_id=_school_id(current),
        limit=limit,
    )


@router.get("/error-book/{student_id}/stats")
async def get_error_book_stats(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_SCORES)),
):
    await _check_student_class_access(db, student_id, current)
    return await service.get_error_book_stats(
        db, student_id=student_id, school_id=_school_id(current),
    )
