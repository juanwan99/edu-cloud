"""学情画像 API 路由 — 成绩趋势/知识点掌握/薄弱诊断/错误模式。"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.core.auth import require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.modules.profile import service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


def _school_id(current: dict) -> str:
    return current["current_role"].school_id


def _snapshot_response(s) -> dict:
    return {
        "id": s.id, "student_id": s.student_id, "exam_id": s.exam_id,
        "subject_code": s.subject_code, "total_score": s.total_score,
        "max_score": s.max_score, "score_rate": s.score_rate,
        "class_rank": s.class_rank, "grade_rank": s.grade_rank,
        "class_size": s.class_size, "grade_size": s.grade_size,
        "knowledge_scores": s.knowledge_scores,
        "exam_date": str(s.exam_date) if s.exam_date else None,
    }


def _mastery_response(m) -> dict:
    return {
        "id": m.id, "student_id": m.student_id,
        "concept_id": m.concept_id,
        "mastery_level": m.mastery_level, "confidence": m.confidence,
        "attempt_count": m.attempt_count, "correct_count": m.correct_count,
        "trend": m.trend, "recent_scores": m.recent_scores,
    }


def _pattern_response(p) -> dict:
    return {
        "id": p.id, "student_id": p.student_id,
        "subject_code": p.subject_code,
        "error_distribution": p.error_distribution,
        "total_errors": p.total_errors, "exam_count": p.exam_count,
    }


@router.get("/students/{student_id}/trend")
async def get_student_trend(
    student_id: str,
    subject_code: str | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_SCORES)),
):
    from edu_cloud.api.permissions import get_visible_subject_codes
    visible_subjects = get_visible_subject_codes(current["current_role"])
    if visible_subjects is not None and subject_code and subject_code not in visible_subjects:
        raise HTTPException(403, "No access to this subject")

    snapshots = await service.get_student_trend(
        db, student_id=student_id, school_id=_school_id(current),
        subject_code=subject_code, limit=limit,
    )
    return [_snapshot_response(s) for s in snapshots]


@router.get("/students/{student_id}/knowledge")
async def get_student_knowledge_map(
    student_id: str,
    course_code: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_SCORES)),
):
    from edu_cloud.api.permissions import get_visible_subject_codes
    visible_subjects = get_visible_subject_codes(current["current_role"])
    if visible_subjects is not None and course_code and course_code not in visible_subjects:
        raise HTTPException(403, "No access to this subject")

    items = await service.get_student_knowledge_map(
        db, student_id=student_id, school_id=_school_id(current),
        course_code=course_code,
    )
    return [_mastery_response(m) for m in items]


@router.get("/students/{student_id}/error-patterns")
async def get_student_error_patterns(
    student_id: str,
    subject_code: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_SCORES)),
):
    from edu_cloud.api.permissions import get_visible_subject_codes
    visible_subjects = get_visible_subject_codes(current["current_role"])
    if visible_subjects is not None and subject_code and subject_code not in visible_subjects:
        raise HTTPException(403, "No access to this subject")

    patterns = await service.get_student_error_pattern(
        db, student_id=student_id, school_id=_school_id(current),
        subject_code=subject_code,
    )
    return [_pattern_response(p) for p in patterns]


@router.get("/class/weakness")
async def get_class_knowledge_weakness(
    class_id: str = Query(...),
    course_code: str | None = Query(None),
    top_n: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_SCORES)),
):
    from edu_cloud.api.permissions import get_visible_class_ids
    from edu_cloud.models.student import Student
    from sqlalchemy import select

    visible_classes = get_visible_class_ids(current["current_role"])
    if visible_classes is not None and class_id not in visible_classes:
        raise HTTPException(403, "No access to this class")

    result = await db.execute(
        select(Student.id).where(
            Student.school_id == _school_id(current),
            Student.class_id == class_id,
        )
    )
    student_ids = [row[0] for row in result.all()]
    if not student_ids:
        return []
    return await service.get_class_knowledge_weakness(
        db, school_id=_school_id(current),
        class_student_ids=student_ids, course_code=course_code, top_n=top_n,
    )


from edu_cloud.modules.profile.diagnosis_service import student_ai_diagnosis


@router.get("/students/{student_id}/ai-diagnosis")
async def get_student_ai_diagnosis(
    student_id: str,
    exam_id: str | None = Query(None),
    subject_code: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.VIEW_SCORES)),
):
    """学生个体 AI 诊断（ORC-007 模板拼接）。"""
    from edu_cloud.models.student import Student
    from edu_cloud.api.permissions import get_visible_class_ids
    from sqlalchemy import select
    role = current["current_role"]
    visible_class_ids = get_visible_class_ids(role)
    if visible_class_ids is not None:
        stu = (await db.execute(
            select(Student.class_id).where(
                Student.id == student_id,
                Student.school_id == _school_id(current),
            )
        )).scalar_one_or_none()
        if stu is None or stu not in visible_class_ids:
            return {"summary": "暂无足够数据生成诊断。", "improving": [], "declining": [], "weak_points": [], "error_patterns": []}
    return await student_ai_diagnosis(
        db, student_id=student_id, school_id=_school_id(current),
        exam_id=exam_id, subject_code=subject_code,
    )
