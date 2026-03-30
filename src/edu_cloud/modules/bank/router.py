"""题库 + 错题本 API 路由。"""
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.modules.bank import service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/bank", tags=["bank"])


def _school_id(current: dict) -> str:
    return current["current_role"].school_id


def _bank_question_response(q) -> dict:
    return {
        "id": q.id, "question_id": q.question_id, "exam_id": q.exam_id,
        "question_type": q.question_type, "max_score": q.max_score,
        "difficulty": q.difficulty, "discrimination": q.discrimination,
        "common_errors": q.common_errors, "attempt_count": q.attempt_count,
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


@router.get("/questions")
async def list_bank_questions(
    question_type: str | None = Query(None),
    min_difficulty: float | None = Query(None),
    max_difficulty: float | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_QUESTION_BANK)),
):
    questions = await service.list_bank_questions(
        db, school_id=_school_id(current),
        question_type=question_type,
        min_difficulty=min_difficulty, max_difficulty=max_difficulty,
        limit=limit,
    )
    return [_bank_question_response(q) for q in questions]


@router.get("/questions/{question_id}")
async def get_bank_question(
    question_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_QUESTION_BANK)),
):
    q = await service.get_bank_question(
        db, bank_question_id=question_id, school_id=_school_id(current),
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
    items = await service.get_student_error_book(
        db, student_id=student_id, school_id=_school_id(current),
        mastery_status=mastery_status, limit=limit,
    )
    return [_error_book_response(e) for e in items]


@router.get("/error-book/{student_id}/stats")
async def get_error_book_stats(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_SCORES)),
):
    return await service.get_error_book_stats(
        db, student_id=student_id, school_id=_school_id(current),
    )
