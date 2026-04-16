import logging
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer, ScanTask
from edu_cloud.modules.scan.service import StorageService, get_storage
from edu_cloud.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/scan", tags=["scan"])


async def _verify_ownership(
    db: AsyncSession, school_id: str, exam_id: str, subject_id: str, question_id: str,
) -> None:
    result = await db.execute(
        select(Exam).where(Exam.id == exam_id, Exam.school_id == school_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Exam not found")
    result = await db.execute(
        select(Subject).where(Subject.id == subject_id, Subject.school_id == school_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Subject not found")
    result = await db.execute(
        select(Question).where(Question.id == question_id, Question.school_id == school_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Question not found")


@router.post("/upload", status_code=201)
async def upload_single(
    exam_id: str = Form(...),
    subject_id: str = Form(...),
    student_id: str = Form(...),
    question_id: str = Form(...),
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
    storage: StorageService = Depends(get_storage),
):
    await _verify_ownership(db, current["current_role"].school_id, exam_id, subject_id, question_id)

    data = await image.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(data) > max_bytes:
        logger.warning("upload_single: file too large, student=%s, size=%d, max=%d", student_id, len(data), max_bytes)
        raise HTTPException(413, f"File too large: {len(data)} bytes, max {max_bytes}")
    path = await storage.save(
        school_id=current["current_role"].school_id,
        exam_id=exam_id,
        subject_id=subject_id,
        question_id=question_id,
        student_id=student_id,
        data=data,
    )
    answer = StudentAnswer(
        exam_id=exam_id,
        subject_id=subject_id,
        student_id=student_id,
        question_id=question_id,
        image_path=path,
        school_id=current["current_role"].school_id,
    )
    db.add(answer)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        try:
            os.remove(path)
        except OSError:
            pass
        logger.warning("upload_single: duplicate, student=%s, question=%s", student_id, question_id)
        raise HTTPException(409, "Answer already exists for this student+question")
    await db.refresh(answer)
    logger.info("upload_single: student=%s, question=%s, exam=%s, size=%d",
                student_id, question_id, exam_id, len(data))
    return {
        "id": answer.id,
        "student_id": answer.student_id,
        "question_id": answer.question_id,
        "image_path": answer.image_path,
    }


@router.post("/upload/batch", status_code=201)
async def upload_batch(
    exam_id: str = Form(...),
    subject_id: str = Form(...),
    student_id: str = Form(...),
    question_ids: str = Form(...),
    images: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
    storage: StorageService = Depends(get_storage),
):
    qids = [q.strip() for q in question_ids.split(",")]
    if len(qids) != len(images):
        raise HTTPException(400, f"question_ids count ({len(qids)}) != images count ({len(images)})")

    # Verify ownership for exam + subject + all questions
    result = await db.execute(
        select(Exam).where(Exam.id == exam_id, Exam.school_id == current["current_role"].school_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Exam not found")
    result = await db.execute(
        select(Subject).where(Subject.id == subject_id, Subject.school_id == current["current_role"].school_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Subject not found")

    uploaded = 0
    errors = []
    saved_paths = []
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    for qid, img in zip(qids, images):
        data = await img.read()
        if len(data) > max_bytes:
            for p in saved_paths:
                try:
                    os.remove(p)
                except OSError:
                    pass
            logger.warning("upload_batch: file too large, student=%s, question=%s, size=%d",
                           student_id, qid, len(data))
            raise HTTPException(413, f"File too large: {len(data)} bytes, max {max_bytes}")
        path = await storage.save(
            school_id=current["current_role"].school_id,
            exam_id=exam_id,
            subject_id=subject_id,
            question_id=qid,
            student_id=student_id,
            data=data,
        )
        saved_paths.append(path)
        answer = StudentAnswer(
            exam_id=exam_id, subject_id=subject_id, student_id=student_id,
            question_id=qid, image_path=path, school_id=current["current_role"].school_id,
        )
        db.add(answer)
        async with db.begin_nested():
            try:
                await db.flush()
                uploaded += 1
            except IntegrityError:
                errors.append(qid)
                try:
                    os.remove(path)
                except OSError:
                    pass

    if uploaded > 0:
        await db.commit()
    logger.info("upload_batch: student=%s, exam=%s, uploaded=%d, errors=%d, error_qids=%s",
                student_id, exam_id, uploaded, len(errors), errors if errors else "none")
    return {"uploaded": uploaded, "errors": errors}


class ScanTaskCreate(BaseModel):
    subject_id: str
    side: Literal["A", "B"] = "A"
    total_images: int = 0
    # 兼容 paper-seg 旧字段名
    total_pages: int | None = None

    def model_post_init(self, __context):
        if self.total_pages and not self.total_images:
            self.total_images = self.total_pages


SCAN_STATUSES = Literal["pending", "processing", "completed", "failed"]


class ScanTaskUpdate(BaseModel):
    processed: int | None = None
    failed: int | None = None
    status: SCAN_STATUSES | None = None
    # 兼容 paper-seg 旧字段名
    processed_pages: int | None = None
    failed_pages: int | None = None

    def model_post_init(self, __context):
        if self.processed_pages is not None and self.processed is None:
            self.processed = self.processed_pages
        if self.failed_pages is not None and self.failed is None:
            self.failed = self.failed_pages


def _task_response(t: ScanTask) -> dict:
    return {
        "id": t.id,
        "subject_id": t.subject_id,
        "side": t.side,
        "status": t.status,
        "total_images": t.total_images,
        "processed": t.processed,
        "failed": t.failed,
    }


@router.post("/tasks", status_code=201)
async def create_scan_task(
    req: ScanTaskCreate,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Subject).where(Subject.id == req.subject_id, Subject.school_id == current["current_role"].school_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Subject not found")

    task = ScanTask(
        subject_id=req.subject_id,
        side=req.side,
        total_images=req.total_images,
        school_id=current["current_role"].school_id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    logger.info("create_scan_task: id=%s, subject=%s, side=%s, total=%d",
                task.id, req.subject_id, req.side, req.total_images)
    return _task_response(task)


@router.patch("/tasks/{task_id}")
async def update_scan_task(
    task_id: str,
    req: ScanTaskUpdate,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(ScanTask).where(ScanTask.id == task_id, ScanTask.school_id == current["current_role"].school_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")
    old_status = task.status
    if req.processed is not None:
        task.processed = req.processed
    if req.failed is not None:
        task.failed = req.failed
    if req.status is not None:
        task.status = req.status
    await db.commit()
    await db.refresh(task)
    if req.status and req.status != old_status:
        logger.info("update_scan_task: id=%s, status=%s→%s, processed=%d, failed=%d",
                     task_id, old_status, task.status, task.processed, task.failed)
    return _task_response(task)


@router.get("/tasks/{task_id}")
async def get_scan_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(ScanTask).where(ScanTask.id == task_id, ScanTask.school_id == current["current_role"].school_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")
    return _task_response(task)


# --------------- objective answer upload ---------------


class ObjectiveAnswer(BaseModel):
    question_id: str
    detected_answer: str
    fill_ratios: dict = {}
    anomaly: bool = False


class UploadObjectiveRequest(BaseModel):
    exam_id: str
    subject_id: str
    student_id: str
    is_absent: bool = False
    answers: list[ObjectiveAnswer] = []


@router.post("/upload-objective")
async def upload_objective(
    req: UploadObjectiveRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    # 1. verify exam ownership
    result = await db.execute(
        select(Exam).where(Exam.id == req.exam_id, Exam.school_id == current["current_role"].school_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Exam not found")

    # 1b. verify subject belongs to this exam
    sub_result = await db.execute(
        select(Subject).where(
            Subject.id == req.subject_id,
            Subject.exam_id == req.exam_id,
            Subject.school_id == current["current_role"].school_id,
        )
    )
    if not sub_result.scalar_one_or_none():
        raise HTTPException(404, "Subject not found in this exam")

    # 2. absent student — score 0 for all questions in this subject
    if req.is_absent:
        q_result = await db.execute(
            select(Question).where(
                Question.subject_id == req.subject_id,
                Question.school_id == current["current_role"].school_id,
            )
        )
        questions = q_result.scalars().all()
        total_max = sum(q.max_score for q in questions)
        for q in questions:
            db.add(StudentAnswer(
                exam_id=req.exam_id,
                subject_id=req.subject_id,
                student_id=req.student_id,
                question_id=q.id,
                score=0,
                is_absent=True,
                school_id=current["current_role"].school_id,
            ))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(409, "Answers already exist for this student")
        logger.info("upload_objective: ABSENT student=%s, exam=%s, questions=%d, total_max=%.1f",
                     req.student_id, req.exam_id, len(questions), total_max)
        return {
            "student_id": req.student_id,
            "is_absent": True,
            "results": [],
            "total_score": 0.0,
            "total_max": total_max,
        }

    # 3. normal grading
    results = []
    total_score = 0.0
    total_max = 0.0
    correct_count = 0
    for ans in req.answers:
        q_result = await db.execute(
            select(Question).where(
                Question.id == ans.question_id,
                Question.school_id == current["current_role"].school_id,
            )
        )
        question = q_result.scalar_one_or_none()
        if not question:
            raise HTTPException(404, f"Question {ans.question_id} not found")

        from edu_cloud.modules.scan.objective_grading import grade_objective_answer
        score, is_correct = grade_objective_answer(ans.detected_answer, question.correct_answer, question.max_score)
        if is_correct:
            correct_count += 1

        db.add(StudentAnswer(
            exam_id=req.exam_id,
            subject_id=req.subject_id,
            student_id=req.student_id,
            question_id=ans.question_id,
            detected_answer=ans.detected_answer,
            score=score,
            is_anomaly=ans.anomaly,
            fill_ratios=ans.fill_ratios,
            school_id=current["current_role"].school_id,
        ))
        total_score += score
        total_max += question.max_score
        results.append({
            "question_id": ans.question_id,
            "detected_answer": ans.detected_answer,
            "correct_answer": question.correct_answer or "",
            "score": score,
            "max_score": question.max_score,
            "is_correct": is_correct,
        })

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Answers already exist for this student")

    logger.info("upload_objective: student=%s, exam=%s, answers=%d, correct=%d/%d, score=%.1f/%.1f",
                req.student_id, req.exam_id, len(req.answers), correct_count, len(req.answers),
                total_score, total_max)

    return {
        "student_id": req.student_id,
        "is_absent": False,
        "results": results,
        "total_score": total_score,
        "total_max": total_max,
    }
