"""Exam / Subject / Question 路由 — 从 exam-ai 迁入。"""
import logging
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user, require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.modules.exam.models import Question, Subject
from edu_cloud.modules.exam import service as exam_service
from edu_cloud.config import settings

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
    question_type: Literal["choice", "multi_choice", "fill_blank", "essay"]
    max_score: float = 0.0
    region_id: str | None = None
    knowledge_points: dict | None = None
    correct_answer: str | None = None


class QuestionUpdate(BaseModel):
    name: str | None = None
    question_type: Literal["choice", "multi_choice", "fill_blank", "essay"] | None = None
    max_score: float | None = None
    region_id: str | None = None
    knowledge_points: dict | None = None
    correct_answer: str | None = None


class QuestionContentUpdate(BaseModel):
    content: str | None = None
    content_images: list | None = None
    reference_answer: str | None = None
    reference_answer_images: list | None = None


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
        "content": q.content,
        "content_images": q.content_images,
        "reference_answer": q.reference_answer,
        "reference_answer_images": q.reference_answer_images,
    }


# ── Exam endpoints ──────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_exam(
    req: ExamCreate,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_EXAMS)),
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
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "题目名称已存在")
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
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "题目名称已存在")
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


@question_router.put("/{question_id}/content")
async def update_question_content(
    question_id: str,
    req: QuestionContentUpdate,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
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
    logger.info("update_question_content: id=%s", question_id)
    return _question_response(q)


@question_router.post("/{question_id}/content/upload-image")
async def upload_question_image(
    question_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
):
    result = await db.execute(
        select(Question).where(Question.id == question_id, Question.school_id == _school_id(current))
    )
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(404, "Question not found")

    ext = Path(file.filename).suffix if file.filename else ".bin"
    filename = f"{uuid.uuid4()}{ext}"
    dest_dir = Path(settings.UPLOAD_DIR) / "questions" / question_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename

    contents = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(413, f"File too large: {len(contents)} bytes")
    from edu_cloud.shared.upload_validation import detect_image_type
    detected = detect_image_type(contents[:32])
    if detected is None:
        raise HTTPException(400, "Invalid image type")
    dest_path.write_bytes(contents)

    url_path = f"/uploads/questions/{question_id}/{filename}"
    logger.info("upload_question_image: question_id=%s path=%s", question_id, url_path)
    return {"path": url_path}


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
    result = await ExamPublishService.publish(db, exam_id=exam_id, school_id=school_id)
    await db.commit()
    return result


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
    await db.commit()
    return {"exam_id": exam_id, "status": "archived"}


# ── Exam Schedule ───────────────────────────────────────────────

class ExamScheduleItem(BaseModel):
    subject_id: str
    exam_start: str | None = None
    exam_end: str | None = None
    exam_room: str | None = None
    proctor_ids: list[str] | None = None


class ExamScheduleBatch(BaseModel):
    subjects: list[ExamScheduleItem]


@router.put("/{exam_id}/schedule")
async def set_exam_schedule(
    exam_id: str,
    body: ExamScheduleBatch,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_EXAMS)),
):
    from datetime import datetime as dt
    from edu_cloud.modules.exam.models import Exam
    exam = await db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(404, "考试不存在")

    for item in body.subjects:
        subject = await db.get(Subject, item.subject_id)
        if not subject or subject.exam_id != exam_id:
            raise HTTPException(400, f"科目 {item.subject_id} 不属于该考试")
        if item.exam_start:
            subject.exam_start = dt.fromisoformat(item.exam_start)
        if item.exam_end:
            subject.exam_end = dt.fromisoformat(item.exam_end)
        subject.exam_room = item.exam_room
        subject.proctor_ids = item.proctor_ids

    # Overlap check
    from edu_cloud.modules.exam.models import Subject as SubjectModel
    stmt = select(SubjectModel).where(SubjectModel.exam_id == exam_id, SubjectModel.exam_start != None)  # noqa: E711
    all_subjects = (await db.execute(stmt)).scalars().all()
    for i, a in enumerate(all_subjects):
        for b in all_subjects[i+1:]:
            if a.exam_start and a.exam_end and b.exam_start and b.exam_end:
                if a.exam_start < b.exam_end and b.exam_start < a.exam_end:
                    raise HTTPException(422, f"科目 {a.name} 和 {b.name} 时间段重叠")

    await db.commit()
    return {"updated": len(body.subjects)}


@router.get("/{exam_id}/schedule")
async def get_exam_schedule(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    from edu_cloud.modules.exam.models import Exam
    exam = await db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(404, "考试不存在")

    stmt = select(Subject).where(Subject.exam_id == exam_id).order_by(Subject.code)
    subjects = (await db.execute(stmt)).scalars().all()

    return {
        "exam_id": exam_id,
        "exam_name": exam.name,
        "subjects": [
            {
                "id": s.id, "name": s.name, "code": s.code,
                "exam_start": s.exam_start.isoformat() if s.exam_start else None,
                "exam_end": s.exam_end.isoformat() if s.exam_end else None,
                "exam_room": s.exam_room,
                "proctor_ids": s.proctor_ids,
            }
            for s in subjects
        ],
    }
