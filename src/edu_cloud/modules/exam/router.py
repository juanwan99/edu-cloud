"""Exam / Subject / Question 路由 — 从 exam-ai 迁入。"""
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user, require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.modules.exam.models import Question, Subject
from edu_cloud.modules.exam import service as exam_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/exams", tags=["exams"])
question_router = APIRouter(prefix="/api/v1/questions", tags=["questions"])


# ── Schemas ──────────────────────────────────────────────────────────

class ExamCreate(BaseModel):
    name: str
    card_title: str


class ExamUpdate(BaseModel):
    name: str | None = None
    card_title: str | None = None
    status: str | None = None


class SubjectCreate(BaseModel):
    name: str
    code: str


class QuestionCreate(BaseModel):
    subject_id: str
    name: str
    question_type: Literal["objective", "subjective"]
    max_score: float = 0.0
    region_id: str | None = None
    knowledge_points: dict | None = None
    correct_answer: str | None = None


class QuestionUpdate(BaseModel):
    name: str | None = None
    question_type: Literal["objective", "subjective"] | None = None
    max_score: float | None = None
    region_id: str | None = None
    knowledge_points: dict | None = None
    correct_answer: str | None = None


# ── Helpers ──────────────────────────────────────────────────────────

def _school_id(current: dict) -> str:
    return current["current_role"].school_id


def _exam_response(e) -> dict:
    return {"id": e.id, "name": e.name, "card_title": e.card_title,
            "school_id": e.school_id, "status": e.status}


def _question_response(q: Question) -> dict:
    return {
        "id": q.id, "subject_id": q.subject_id, "name": q.name,
        "question_type": q.question_type, "max_score": q.max_score,
        "region_id": q.region_id, "knowledge_points": q.knowledge_points,
        "correct_answer": q.correct_answer,
    }


# ── Exam endpoints ──────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_exam(
    req: ExamCreate,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    exam = await exam_service.create_exam(
        db, name=req.name, card_title=req.card_title, school_id=_school_id(current),
    )
    return _exam_response(exam)


@router.get("")
async def list_exams(
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    exams = await exam_service.list_exams(db, school_id=_school_id(current))
    return [_exam_response(e) for e in exams]


@router.get("/{exam_id}")
async def get_exam(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    exam = await exam_service.get_exam(db, exam_id=exam_id, school_id=_school_id(current))
    return _exam_response(exam)


@router.patch("/{exam_id}")
async def update_exam(
    exam_id: str,
    req: ExamUpdate,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    exam = await exam_service.update_exam(
        db, exam_id=exam_id, school_id=_school_id(current),
        name=req.name, card_title=req.card_title, status=req.status,
    )
    return _exam_response(exam)


@router.post("/{exam_id}/subjects", status_code=201)
async def create_subject(
    exam_id: str,
    req: SubjectCreate,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    subject = await exam_service.create_subject(
        db, exam_id=exam_id, name=req.name, code=req.code, school_id=_school_id(current),
    )
    return {"id": subject.id, "exam_id": subject.exam_id, "name": subject.name, "code": subject.code}


@router.get("/{exam_id}/subjects")
async def list_subjects(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    subjects = await exam_service.list_subjects(db, exam_id=exam_id, school_id=_school_id(current))
    return [{"id": s.id, "exam_id": s.exam_id, "name": s.name, "code": s.code} for s in subjects]


# ── Question endpoints ──────────────────────────────────────────────

@question_router.post("", status_code=201)
async def create_question(
    req: QuestionCreate,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    sid = _school_id(current)
    result = await db.execute(
        select(Subject).where(Subject.id == req.subject_id, Subject.school_id == sid)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Subject not found")
    q = Question(
        subject_id=req.subject_id, name=req.name, question_type=req.question_type,
        max_score=req.max_score, region_id=req.region_id,
        knowledge_points=req.knowledge_points, correct_answer=req.correct_answer,
        school_id=sid,
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)
    logger.info("create_question: id=%s, name=%s, subject=%s", q.id, q.name, req.subject_id)
    return _question_response(q)


@question_router.get("")
async def list_questions(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Question).where(Question.subject_id == subject_id, Question.school_id == _school_id(current))
    )
    return [_question_response(q) for q in result.scalars().all()]


@question_router.get("/{question_id}")
async def get_question(
    question_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Question).where(Question.id == question_id, Question.school_id == _school_id(current))
    )
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(404, "Question not found")
    return _question_response(q)


@question_router.patch("/{question_id}")
async def update_question(
    question_id: str,
    req: QuestionUpdate,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Question).where(Question.id == question_id, Question.school_id == _school_id(current))
    )
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(404, "Question not found")
    updates = req.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(q, field, value)
    await db.commit()
    await db.refresh(q)
    return _question_response(q)


@question_router.delete("/{question_id}")
async def delete_question(
    question_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Question).where(Question.id == question_id, Question.school_id == _school_id(current))
    )
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(404, "Question not found")
    await db.delete(q)
    await db.commit()
    return {"deleted": True, "id": question_id}


# ── Publish / Archive ────────────��─────────────────────────────────

@router.post("/{exam_id}/publish")
async def publish_exam(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_EXAM_RESULTS)),
):
    from edu_cloud.modules.exam.publish_service import ExamPublishService
    from edu_cloud.modules.exam.models import Exam
    school_id = _school_id(current)
    if not school_id:
        # platform_admin: derive school_id from exam
        exam = await db.get(Exam, exam_id)
        if not exam:
            raise HTTPException(404, "Exam not found")
        school_id = exam.school_id
    return await ExamPublishService.publish(db, exam_id=exam_id, school_id=school_id)


@router.post("/{exam_id}/archive")
async def archive_exam(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_EXAM_RESULTS)),
):
    from edu_cloud.modules.exam.publish_service import ExamPublishService
    from edu_cloud.modules.exam.models import Exam
    school_id = _school_id(current)
    if not school_id:
        exam = await db.get(Exam, exam_id)
        if not exam:
            raise HTTPException(404, "Exam not found")
        school_id = exam.school_id
    await ExamPublishService.archive(db, exam_id=exam_id, school_id=school_id)
    return {"exam_id": exam_id, "status": "archived"}
