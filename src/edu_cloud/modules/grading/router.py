import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user
from edu_cloud.modules.exam.models import Exam, Question, Subject, QUESTION_TYPES_SUBJECTIVE
from edu_cloud.modules.grading.models import Rubric, GradingTask, GradingResult
from edu_cloud.modules.scan.models import StudentAnswer
from datetime import datetime, timezone

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
    school_id = current["current_role"].school_id

    # 前置校验 1：Subject 归属
    result = await db.execute(
        select(Subject).where(
            Subject.id == req.subject_id,
            Subject.school_id == school_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Subject not found")

    # 前置校验 2：至少 1 道主观题（L72 worker fast-path 会 trivially completed）
    subjective_q_ids = (await db.execute(
        select(Question.id).where(
            Question.subject_id == req.subject_id,
            Question.school_id == school_id,
            Question.question_type.in_(QUESTION_TYPES_SUBJECTIVE),
        )
    )).scalars().all()
    if not subjective_q_ids:
        raise HTTPException(400, "该科目无主观题，无需 AI 阅卷")

    # 前置校验 3：主观题已配置评分标准 Rubric（L120 worker 每条 answer 都会 failed）
    rubric_count = (await db.execute(
        select(func.count(Rubric.id)).where(
            Rubric.question_id.in_(subjective_q_ids),
            Rubric.school_id == school_id,
        )
    )).scalar() or 0
    if rubric_count == 0:
        raise HTTPException(400, "请先为主观题配置评分标准（Rubric）后再启动 AI 阅卷")

    # 前置校验 4：至少 1 条 StudentAnswer（worker total=0 虚假 completed）
    answer_count = (await db.execute(
        select(func.count(StudentAnswer.id)).where(
            StudentAnswer.subject_id == req.subject_id,
            StudentAnswer.school_id == school_id,
            StudentAnswer.question_id.in_(subjective_q_ids),
        )
    )).scalar() or 0
    if answer_count == 0:
        raise HTTPException(400, "该科目暂无可批改答卷，请先完成扫描与切图")

    # 创建 task（commit 以获得 ID），后续 enqueue 失败则清理 orphan
    task = GradingTask(
        subject_id=req.subject_id,
        school_id=school_id,
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

    # F007 orphan 防御：enqueue 失败必须清理已落库的 GradingTask
    try:
        await enqueue_grading_task(task.id)
    except Exception as e:
        logger.error(
            "create_grading_task: enqueue failed, cleaning up orphan task=%s, error=%s",
            task.id, e, exc_info=True,
        )
        await db.delete(task)
        await db.commit()
        raise HTTPException(503, f"任务队列暂不可用，请稍后重试: {e}")

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

def _result_response(r: GradingResult) -> dict:
    return {
        "id": r.id,
        "task_id": r.ai_task_id,
        "answer_id": r.answer_id,
        "question_id": r.question_id,
        "ai_score": r.ai_score,
        "final_score": r.final_score,
        "max_score": r.max_score,
        "ai_feedback": r.ai_feedback,
        "ai_confidence": r.ai_confidence,
        "status": r.status,
        "source": r.source,
        "reviewer_id": r.reviewer_id,
        "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
        "review_comment": r.review_comment,
        "version": r.version,
    }


# --- Result routes ---

@router.get("/results")
async def list_results(
    task_id: str | None = None,
    question_id: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    stmt = select(GradingResult).where(GradingResult.school_id == current["current_role"].school_id)
    if task_id:
        stmt = stmt.where(GradingResult.ai_task_id == task_id)
    if question_id:
        stmt = stmt.where(GradingResult.question_id == question_id)
    if status:
        stmt = stmt.where(GradingResult.status == status)
    result = await db.execute(stmt)
    results = result.scalars().all()
    logger.debug("list_results: filters={task=%s, question=%s, status=%s}, count=%d",
                 task_id, question_id, status, len(results))
    return [_result_response(r) for r in results]


@router.get("/review/pending")
async def list_pending_reviews(
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """返回 AI 已评但待教师确认的记录（status='ai_done'）。"""
    result = await db.execute(
        select(GradingResult).where(
            GradingResult.school_id == current["current_role"].school_id,
            GradingResult.status == "ai_done",
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
        select(GradingResult).where(
            GradingResult.id == result_id,
            GradingResult.school_id == current["current_role"].school_id,
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
    """教师对 AI 评分进行 approve / override 确认。

    approve  → status=confirmed, source=ai, final_score 不变
    override → status=confirmed, source=ai_override, final_score=adjusted_score
    """
    result = await db.execute(
        select(GradingResult).where(
            GradingResult.id == result_id,
            GradingResult.school_id == current["current_role"].school_id,
        )
    )
    gr = result.scalar_one_or_none()
    if not gr:
        raise HTTPException(404, "Result not found")

    if gr.status == "confirmed":
        logger.warning("submit_review: already confirmed, result=%s, source=%s",
                       result_id, gr.source)
        raise HTTPException(409, "Already reviewed")
    if gr.status != "ai_done":
        raise HTTPException(400, f"Cannot review result in status '{gr.status}'")

    if req.action == "override" and req.adjusted_score is None:
        raise HTTPException(400, "adjusted_score is required for override")

    now = datetime.now(timezone.utc)
    if req.action == "approve":
        gr.source = "ai"
    else:
        gr.source = "ai_override"
        gr.final_score = req.adjusted_score
    gr.status = "confirmed"
    gr.reviewer_id = current["user"].id
    gr.reviewed_at = now
    gr.review_comment = req.comment
    gr.version = gr.version + 1

    await db.commit()
    await db.refresh(gr)

    logger.info("submit_review: result=%s, action=%s, reviewer=%s, ai_score=%s, final_score=%s",
                result_id, req.action, current["user"].username, gr.ai_score, gr.final_score)

    return _result_response(gr)


@router.get("/dispatch/status")
async def get_dispatch_status(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """聚合该考试所有科目的阅卷调度状态。"""
    school_id = current["current_role"].school_id

    # 验证考试归属
    exam = (await db.execute(
        select(Exam).where(Exam.id == exam_id, Exam.school_id == school_id)
    )).scalar_one_or_none()
    if not exam:
        raise HTTPException(404, "Exam not found")

    # 获取所有科目
    subjects = (await db.execute(
        select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
    )).scalars().all()

    from edu_cloud.modules.scan import pipeline_service

    result = []
    for subj in subjects:
        # 统计 StudentAnswer
        answer_count = (await db.execute(
            select(func.count(StudentAnswer.id)).where(
                StudentAnswer.subject_id == subj.id,
                StudentAnswer.school_id == school_id,
            )
        )).scalar() or 0

        # 统计选择题（有 detected_answer 的）
        objective_graded = (await db.execute(
            select(func.count(StudentAnswer.id)).where(
                StudentAnswer.subject_id == subj.id,
                StudentAnswer.school_id == school_id,
                StudentAnswer.detected_answer.isnot(None),
            )
        )).scalar() or 0

        # 查 GradingTask
        grading_task = (await db.execute(
            select(GradingTask).where(
                GradingTask.subject_id == subj.id,
                GradingTask.school_id == school_id,
            ).order_by(GradingTask.created_at.desc())
        )).scalars().first()

        # 统计 GradingResult 校对状态
        reviewed = 0
        ai_graded = 0
        ai_failed = 0
        grading_task_id = None
        if grading_task:
            grading_task_id = grading_task.id
            ai_graded = grading_task.completed
            ai_failed = grading_task.failed
            reviewed = (await db.execute(
                select(func.count(GradingResult.id)).where(
                    GradingResult.ai_task_id == grading_task.id,
                    GradingResult.status == "confirmed",
                )
            )).scalar() or 0

        # F011 修复：subjective_total 查询提前到 stage 推导之前
        subjective_total = (await db.execute(
            select(func.count(StudentAnswer.id)).where(
                StudentAnswer.subject_id == subj.id,
                StudentAnswer.school_id == school_id,
                StudentAnswer.image_path.isnot(None),
            )
        )).scalar() or 0

        # 推导 stage（INV-003: ready 条件与 POST /grading/tasks 前置校验一致）
        has_subjective_answers = subjective_total > 0
        subjective_q_ids = (await db.execute(
            select(Question.id).where(
                Question.subject_id == subj.id,
                Question.school_id == school_id,
                Question.question_type.in_(QUESTION_TYPES_SUBJECTIVE),
            )
        )).scalars().all()
        has_rubric = False
        if subjective_q_ids:
            rubric_count = (await db.execute(
                select(func.count(Rubric.id)).where(
                    Rubric.question_id.in_(subjective_q_ids),
                    Rubric.school_id == school_id,
                )
            )).scalar() or 0
            has_rubric = rubric_count > 0
        can_ai_grade = has_subjective_answers and has_rubric and len(subjective_q_ids) > 0

        is_cutting = (
            pipeline_service.is_running()
            and pipeline_service.get_progress().get("current_subject_id") == subj.id
        )
        if is_cutting:
            stage = "cutting"
        elif answer_count == 0:
            stage = "idle"
        elif not grading_task and can_ai_grade:
            stage = "ready"
        elif not grading_task:
            stage = "idle"  # 有选择题答案但无主观题/Rubric，不算 ready
        elif grading_task.status == "failed":
            stage = "failed"  # F005: 显式处理 failed，不折叠成 done
        elif grading_task.status in ("pending", "processing"):
            stage = "ai_grading"
        elif grading_task.status == "completed" and reviewed < ai_graded:
            stage = "reviewing"
        else:
            stage = "done"

        result.append({
            "subject_id": subj.id,
            "subject_name": subj.name,
            "stage": stage,
            "scan_images": answer_count,
            "objective_total": objective_graded,
            "objective_graded": objective_graded,
            "subjective_total": subjective_total,
            "ai_graded": ai_graded,
            "ai_failed": ai_failed,
            "reviewed": reviewed,
            "grading_task_id": grading_task_id,
        })

    return result
