"""Exam / Subject 业务逻辑（从 exam-ai 迁入）。"""
import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.services.exceptions import NotFoundError, ValidationError, ConflictError

logger = logging.getLogger(__name__)

_VALID_STATUS_TRANSITIONS = {
    "draft": {"scanning"},
    "scanning": {"grading", "draft"},
    "grading": {"reviewing"},
    "reviewing": {"completed"},
    # published 和 archived 只能通过 ExamPublishService 进入，不在此字典中
}

# published/archived 只能通过 ExamPublishService 进入，update_exam 不允许
_PUBLISH_ONLY_STATUSES = {"published", "archived"}


async def create_exam(
    db: AsyncSession, *, name: str, card_title: str, school_id: str
) -> Exam:
    exam = Exam(name=name, card_title=card_title, school_id=school_id)
    db.add(exam)
    await db.commit()
    await db.refresh(exam)
    logger.info("create_exam: id=%s, name=%s, school=%s", exam.id, exam.name, school_id)
    return exam


async def list_exams(db: AsyncSession, *, school_id: str) -> list[Exam]:
    result = await db.execute(
        select(Exam).where(Exam.school_id == school_id)
    )
    exams = list(result.scalars().all())
    logger.debug("list_exams: school=%s, count=%d", school_id, len(exams))
    return exams


async def get_exam(db: AsyncSession, *, exam_id: str, school_id: str) -> Exam:
    result = await db.execute(
        select(Exam).where(Exam.id == exam_id, Exam.school_id == school_id)
    )
    exam = result.scalar_one_or_none()
    if not exam:
        raise NotFoundError("Exam not found")
    return exam


async def update_exam(
    db: AsyncSession,
    *,
    exam_id: str,
    school_id: str,
    name: str | None = None,
    card_title: str | None = None,
    status: str | None = None,
) -> Exam:
    exam = await get_exam(db, exam_id=exam_id, school_id=school_id)
    changes = {}
    if name is not None:
        changes["name"] = (exam.name, name)
        exam.name = name
    if card_title is not None:
        changes["card_title"] = (exam.card_title, card_title)
        exam.card_title = card_title
    if status is not None:
        if status in _PUBLISH_ONLY_STATUSES:
            raise ValidationError(
                f"无效的状态变更: {status} 只能通过 ExamPublishService 设置"
            )
        allowed = _VALID_STATUS_TRANSITIONS.get(exam.status, set())
        if status not in allowed:
            raise ValidationError(f"无效的状态变更: {exam.status} → {status}")
        changes["status"] = (exam.status, status)
        exam.status = status
    await db.commit()
    await db.refresh(exam)
    if changes:
        logger.info(
            "update_exam: id=%s, changes=%s",
            exam_id,
            {k: f"{old}→{new}" for k, (old, new) in changes.items()},
        )
    # DF-001: 考试状态 → completed 时自动触发数据流水线
    if status == "completed":
        try:
            from edu_cloud.modules.pipeline.service import run_full_pipeline
            results = await run_full_pipeline(db, exam_id=exam_id, school_id=school_id)
            logger.info("auto_pipeline: exam=%s, results=%s", exam_id, results)
        except Exception:
            logger.error("auto_pipeline failed: exam=%s", exam_id, exc_info=True)
    return exam


async def create_subject(
    db: AsyncSession, *, exam_id: str, name: str, code: str, school_id: str
) -> Subject:
    await get_exam(db, exam_id=exam_id, school_id=school_id)
    subject = Subject(exam_id=exam_id, name=name, code=code, school_id=school_id)
    db.add(subject)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        logger.warning("create_subject: duplicate code=%s, exam=%s", code, exam_id)
        raise ConflictError("Subject code already exists for this exam")
    await db.refresh(subject)
    logger.info("create_subject: id=%s, code=%s, name=%s, exam=%s", subject.id, code, name, exam_id)
    return subject


async def list_subjects(
    db: AsyncSession, *, exam_id: str, school_id: str
) -> list[Subject]:
    result = await db.execute(
        select(Subject).where(
            Subject.exam_id == exam_id, Subject.school_id == school_id
        )
    )
    return list(result.scalars().all())


async def list_questions(
    db: AsyncSession, *, subject_id: str, school_id: str
) -> list[Question]:
    result = await db.execute(
        select(Question).where(
            Question.subject_id == subject_id, Question.school_id == school_id,
        )
    )
    return list(result.scalars().all())
