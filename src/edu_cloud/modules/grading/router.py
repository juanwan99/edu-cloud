import base64
import logging
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user, require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.config import settings
from edu_cloud.modules.exam.models import Exam, Question, Subject, QUESTION_TYPES_SUBJECTIVE
from edu_cloud.modules.grading.models import Rubric, GradingTask, GradingResult
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.card.models import Template
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/grading", tags=["grading"])

# --- 子路由注册 ---
from edu_cloud.modules.grading.grading_review_router import router as review_sub_router
router.include_router(review_sub_router)


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


def _validate_criteria(criteria: list[dict], question_max_score: float) -> None:
    """Validate rubric criteria list.

    Raises HTTPException 422 on:
    - Missing or empty blankNo
    - Missing or non-numeric score, or score < 0
    - Missing or empty answer
    - Sum of scores != question max_score
    """
    if not criteria:
        raise HTTPException(422, "criteria must not be empty")

    total = 0.0
    for i, item in enumerate(criteria):
        blank_no = item.get("blankNo")
        if not blank_no or not isinstance(blank_no, str) or not blank_no.strip():
            raise HTTPException(422, f"criteria[{i}] missing or empty blankNo")

        score = item.get("score")
        if score is None or not isinstance(score, (int, float)):
            raise HTTPException(422, f"criteria[{i}] missing numeric score")
        if score < 0:
            raise HTTPException(422, f"criteria[{i}] score must be >= 0, got {score}")

        answer = item.get("standardAnswer") or item.get("answer")
        if not answer or not isinstance(answer, str) or not answer.strip():
            raise HTTPException(422, f"criteria[{i}] missing standardAnswer or answer")

        total += score

    # Use a small tolerance for float comparison
    if abs(total - question_max_score) > 1e-6:
        raise HTTPException(
            422,
            f"Sum of criteria scores ({total}) must equal question max_score ({question_max_score})",
        )


# --- Rubric generation helper ---

async def generate_rubric_via_llm(
    question: Question,
    max_score: float,
    db: AsyncSession,
) -> list[dict]:
    """Build prompt and call LLM to generate rubric criteria.

    Module-level function so it can be mocked in tests.
    """
    from edu_cloud.modules.grading.prompts_legacy import build_rubric_generation_prompt
    from edu_cloud.modules.grading.llm_client import LLMClient

    content = question.content or ""
    reference_answer = question.reference_answer or ""

    # Collect image paths from question (content_images + reference_answer_images)
    all_image_paths: list[str] = []
    if question.content_images:
        all_image_paths.extend(question.content_images)
    if question.reference_answer_images:
        all_image_paths.extend(question.reference_answer_images)

    # Convert local image paths to base64
    upload_root = Path(settings.UPLOAD_DIR).resolve()
    images_b64: list[str] = []
    for img_path in all_image_paths:
        if img_path.startswith("/uploads/"):
            local = upload_root / img_path.split("/uploads/", 1)[1]
        else:
            local = upload_root / img_path
        try:
            local = local.resolve()
        except Exception:
            continue
        if local.exists() and str(local).startswith(str(upload_root)):
            try:
                with open(local, "rb") as f:
                    images_b64.append(base64.b64encode(f.read()).decode())
            except OSError:
                logger.warning("generate_rubric_via_llm: cannot read image %s", local)

    messages = build_rubric_generation_prompt(
        content=content,
        reference_answer=reference_answer,
        max_score=max_score,
        question_type=question.question_type,
    )

    client = LLMClient(
        api_url=settings.LLM_API_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        timeout=settings.LLM_TIMEOUT,
        max_retries=settings.LLM_MAX_RETRIES,
        slot=settings.LLM_SLOT,
    )
    try:
        return await client.generate_rubric(messages, images_b64=images_b64 or None)
    finally:
        await client.close()


# --- Rubric generate schema ---

class RubricGenerateRequest(BaseModel):
    question_id: str
    max_score: float


# --- Rubric routes ---

@router.post("/rubrics", status_code=201)
async def create_or_update_rubric(
    req: RubricCreate,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
):
    # Verify question belongs to this tenant
    q_result = await db.execute(
        select(Question).where(
            Question.id == req.question_id,
            Question.school_id == current["current_role"].school_id,
        )
    )
    question = q_result.scalar_one_or_none()
    if not question:
        raise HTTPException(404, "Question not found")

    # Validate criteria before saving
    _validate_criteria(req.criteria, question.max_score)

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


@router.post("/rubrics/generate")
async def generate_rubric_endpoint(
    req: RubricGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
):
    """AI 生成评分细则（Rubric）。

    - 查 Question（校验归属）
    - 校验 content 或 reference_answer 非空
    - 调用 LLM 生成 criteria
    - Upsert Rubric（source=ai_generated）
    - 返回 rubric 响应
    """
    school_id = current["current_role"].school_id

    # Query question with content fields
    q_result = await db.execute(
        select(Question).where(
            Question.id == req.question_id,
            Question.school_id == school_id,
        )
    )
    question = q_result.scalar_one_or_none()
    if not question:
        raise HTTPException(404, "Question not found")

    # Both content and reference_answer empty → 400
    if not (question.content or "").strip() and not (question.reference_answer or "").strip():
        raise HTTPException(400, "Question has no content or reference_answer; cannot generate rubric")

    # Call LLM (mocked in tests via patch on generate_rubric_via_llm)
    # Use question.max_score from DB (not client req.max_score) for correctness
    criteria = await generate_rubric_via_llm(question, question.max_score, db)

    # Validate LLM-generated criteria before persisting
    _validate_criteria(criteria, question.max_score)

    logger.info(
        "generate_rubric_endpoint: question=%s, max_score=%s, criteria=%d items",
        req.question_id, question.max_score, len(criteria),
    )

    # Upsert Rubric with source=ai_generated
    result = await db.execute(
        select(Rubric).where(
            Rubric.question_id == req.question_id,
            Rubric.school_id == school_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.criteria = criteria
        existing.source = "ai_generated"
        await db.commit()
        await db.refresh(existing)
        return _rubric_response(existing)

    rubric = Rubric(
        question_id=req.question_id,
        criteria=criteria,
        source="ai_generated",
        school_id=school_id,
    )
    db.add(rubric)
    await db.commit()
    await db.refresh(rubric)
    return _rubric_response(rubric)


# --- Task schemas ---

class GradingTaskCreate(BaseModel):
    subject_id: str
    question_id: str | None = None


def _task_response(t: GradingTask) -> dict:
    return {
        "id": t.id,
        "subject_id": t.subject_id,
        "question_id": t.question_id,
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
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
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

    if req.question_id:
        # --- Question-level path ---
        # AGP-001: validate question belongs to subject AND is subjective
        q_row = (await db.execute(
            select(Question).where(
                Question.id == req.question_id,
                Question.subject_id == req.subject_id,
                Question.school_id == school_id,
                Question.question_type.in_(QUESTION_TYPES_SUBJECTIVE),
            )
        )).scalar_one_or_none()
        if not q_row:
            raise HTTPException(400, "该题目不存在、不属于该科目或非主观题")

        # Check Rubric exists for this question
        rubric_exists = (await db.execute(
            select(func.count(Rubric.id)).where(
                Rubric.question_id == req.question_id,
                Rubric.school_id == school_id,
            )
        )).scalar() or 0
        if rubric_exists == 0:
            raise HTTPException(400, "请先为该题目配置评分标准（Rubric）")

        # Check StudentAnswer exists for this question
        ans_count = (await db.execute(
            select(func.count(StudentAnswer.id)).where(
                StudentAnswer.question_id == req.question_id,
                StudentAnswer.school_id == school_id,
            )
        )).scalar() or 0
        if ans_count == 0:
            raise HTTPException(400, "该题目暂无可批改答卷")

        # AGP-004: Regrade semantics - clean old ai_pending/ai_done results
        old_results = (await db.execute(
            select(GradingResult).where(
                GradingResult.question_id == req.question_id,
                GradingResult.school_id == school_id,
                GradingResult.status.in_(["ai_pending", "ai_done"]),
            )
        )).scalars().all()
        for old in old_results:
            await db.delete(old)
        if old_results:
            await db.commit()
            logger.info("create_grading_task: cleaned %d stale results for question=%s",
                        len(old_results), req.question_id)

    else:
        # --- Subject-level path (ORC-002: unchanged) ---
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

        # Subject-level: clean old ai_pending/ai_done results for all subjective questions
        old_results = (await db.execute(
            select(GradingResult).where(
                GradingResult.question_id.in_(subjective_q_ids),
                GradingResult.school_id == school_id,
                GradingResult.status.in_(["ai_pending", "ai_done"]),
            )
        )).scalars().all()
        for old in old_results:
            await db.delete(old)
        if old_results:
            await db.commit()
            logger.info("create_grading_task: cleaned %d stale subject-level results", len(old_results))

    # 创建 task（commit 以获得 ID），后续 enqueue 失败则清理 orphan
    task = GradingTask(
        subject_id=req.subject_id,
        question_id=req.question_id,  # None for subject-level
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


