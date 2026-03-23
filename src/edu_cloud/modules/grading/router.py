import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user
from edu_cloud.modules.exam.models import Question, Subject
from edu_cloud.modules.grading.models import Rubric, GradingTask, AIGradingResult, TeacherReview
from edu_cloud.modules.scan.models import StudentAnswer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/grading", tags=["grading"])


# --- Schemas ---

class RubricCreate(BaseModel):
    question_id: str
    criteria: list[dict]
    reference_answer: str | None = None
    source: Literal["manual", "ai_generated"] = "manual"


def _rubric_response(r: Rubric) -> dict:
    return {
        "id": r.id,
        "question_id": r.question_id,
        "criteria": r.criteria,
        "reference_answer": r.reference_answer,
        "source": r.source,
    }


# --- Rubric routes ---

@router.post("/rubrics", status_code=201)
async def create_or_update_rubric(
    req: RubricCreate,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    # Verify question belongs to this tenant
    q_result = await db.execute(
        select(Question).where(
            Question.id == req.question_id,
            Question.school_id == current["current_role"].school_id,
        )
    )
    if not q_result.scalar_one_or_none():
        raise HTTPException(404, "Question not found")

    # Upsert: if rubric exists for this question, update it
    result = await db.execute(
        select(Rubric).where(
            Rubric.question_id == req.question_id,
            Rubric.school_id == current["current_role"].school_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.criteria = req.criteria
        existing.reference_answer = req.reference_answer
        existing.source = req.source
        await db.commit()
        await db.refresh(existing)
        logger.info("update_rubric: question=%s, criteria=%d items", req.question_id, len(req.criteria))
        return _rubric_response(existing)

    rubric = Rubric(
        question_id=req.question_id,
        criteria=req.criteria,
        reference_answer=req.reference_answer,
        source=req.source,
        school_id=current["current_role"].school_id,
    )
    db.add(rubric)
    await db.commit()
    await db.refresh(rubric)
    logger.info("create_rubric: id=%s, question=%s, source=%s, criteria=%d items",
                rubric.id, req.question_id, req.source, len(req.criteria))
    return _rubric_response(rubric)


@router.get("/rubrics/{question_id}")
async def get_rubric(
    question_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Rubric).where(
            Rubric.question_id == question_id,
            Rubric.school_id == current["current_role"].school_id,
        )
    )
    rubric = result.scalar_one_or_none()
    if not rubric:
        raise HTTPException(404, "Rubric not found")
    return _rubric_response(rubric)


# --- Task schemas ---

class GradingTaskCreate(BaseModel):
    subject_id: str


def _task_response(t: GradingTask) -> dict:
    return {
        "id": t.id,
        "subject_id": t.subject_id,
        "status": t.status,
        "total": t.total,
        "completed": t.completed,
        "failed": t.failed,
        "created_by": t.created_by,
        "error_log": t.error_log,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


async def enqueue_grading_task(task_id: str) -> None:
    """Enqueue an arq job. Separated for testability (mock in tests)."""
    from arq import create_pool
    from arq.connections import RedisSettings
    from edu_cloud.config import settings
    redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    try:
        await redis.enqueue_job("process_grading_task", task_id)
        logger.info("enqueue_grading_task: task=%s queued to Redis", task_id)
    except Exception:
        logger.error("enqueue_grading_task: failed to queue task=%s", task_id, exc_info=True)
        raise
    finally:
        await redis.close()


# --- Task routes ---

@router.post("/tasks", status_code=201)
async def create_grading_task(
    req: GradingTaskCreate,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    # Verify subject belongs to tenant
    result = await db.execute(
        select(Subject).where(
            Subject.id == req.subject_id,
            Subject.school_id == current["current_role"].school_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Subject not found")

    task = GradingTask(
        subject_id=req.subject_id,
        school_id=current["current_role"].school_id,
        status="pending",
        total=0,
        completed=0,
        failed=0,
        created_by=current["user"].id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    logger.info("create_grading_task: id=%s, subject=%s, created_by=%s",
                task.id, req.subject_id, current["user"].username)
    await enqueue_grading_task(task.id)

    return _task_response(task)


@router.get("/tasks")
async def list_grading_tasks(
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(GradingTask)
        .where(GradingTask.school_id == current["current_role"].school_id)
        .order_by(GradingTask.created_at.desc())
    )
    return [_task_response(t) for t in result.scalars().all()]


@router.get("/tasks/{task_id}")
async def get_grading_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(GradingTask).where(
            GradingTask.id == task_id,
            GradingTask.school_id == current["current_role"].school_id,
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")
    return _task_response(task)


# --- Result schemas ---

def _result_response(r: AIGradingResult) -> dict:
    return {
        "id": r.id,
        "task_id": r.task_id,
        "answer_id": r.answer_id,
        "question_id": r.question_id,
        "score": r.score,
        "max_score": r.max_score,
        "feedback": r.feedback,
        "confidence": r.confidence,
        "review_status": r.review_status,
    }


# --- Result routes ---

@router.get("/results")
async def list_results(
    task_id: str | None = None,
    question_id: str | None = None,
    review_status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    stmt = select(AIGradingResult).where(AIGradingResult.school_id == current["current_role"].school_id)
    if task_id:
        stmt = stmt.where(AIGradingResult.task_id == task_id)
    if question_id:
        stmt = stmt.where(AIGradingResult.question_id == question_id)
    if review_status:
        stmt = stmt.where(AIGradingResult.review_status == review_status)
    result = await db.execute(stmt)
    results = result.scalars().all()
    logger.debug("list_results: filters={task=%s, question=%s, status=%s}, count=%d",
                 task_id, question_id, review_status, len(results))
    return [_result_response(r) for r in results]


@router.get("/review/pending")
async def list_pending_reviews(
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(AIGradingResult).where(
            AIGradingResult.school_id == current["current_role"].school_id,
            AIGradingResult.review_status == "pending",
        )
    )
    pending = result.scalars().all()
    logger.debug("list_pending_reviews: count=%d", len(pending))
    return [_result_response(r) for r in pending]


@router.get("/results/{result_id}")
async def get_result(
    result_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(AIGradingResult).where(
            AIGradingResult.id == result_id,
            AIGradingResult.school_id == current["current_role"].school_id,
        )
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "Result not found")
    return _result_response(r)


# --- Review schemas ---

class ReviewCreate(BaseModel):
    action: Literal["approve", "override"]
    adjusted_score: float | None = None
    comment: str | None = None


# --- Review routes ---

@router.post("/review/{result_id}")
async def submit_review(
    result_id: str,
    req: ReviewCreate,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(AIGradingResult).where(
            AIGradingResult.id == result_id,
            AIGradingResult.school_id == current["current_role"].school_id,
        )
    )
    ai_result = result.scalar_one_or_none()
    if not ai_result:
        raise HTTPException(404, "Result not found")

    if ai_result.review_status != "pending":
        logger.warning("submit_review: already reviewed, result=%s, status=%s", result_id, ai_result.review_status)
        raise HTTPException(409, "Already reviewed")

    if req.action == "override" and req.adjusted_score is None:
        raise HTTPException(400, "adjusted_score is required for override")

    review = TeacherReview(
        result_id=result_id,
        reviewer_id=current["user"].id,
        school_id=current["current_role"].school_id,
        action=req.action,
        adjusted_score=req.adjusted_score,
        comment=req.comment,
    )
    db.add(review)

    ai_result.review_status = "approved" if req.action == "approve" else "overridden"
    await db.commit()
    await db.refresh(ai_result)

    logger.info("submit_review: result=%s, action=%s, reviewer=%s, ai_score=%.1f%s",
                result_id, req.action, current["user"].username, ai_result.score,
                f", adjusted={req.adjusted_score}" if req.adjusted_score is not None else "")

    resp = _result_response(ai_result)
    if req.adjusted_score is not None:
        resp["adjusted_score"] = req.adjusted_score
    return resp
