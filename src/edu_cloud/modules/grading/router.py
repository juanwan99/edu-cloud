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
from edu_cloud.logging_config import business_event
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

    Uses the new prompts system (subject-specific build_rubric_generation)
    with Gemini official SDK. Falls back to legacy LLMClient if Gemini unavailable.
    """
    from edu_cloud.modules.grading.prompts import get_prompt, render_prompt
    from edu_cloud.modules.grading.gemini_client import GeminiClient, _make_image_part
    from edu_cloud.modules.grading.json_parser import extract_json
    from google.genai import types

    content = question.content or ""
    reference_answer = question.reference_answer or ""

    # Determine subject code for prompt selection
    subject_result = await db.execute(
        select(Subject).where(Subject.id == question.subject_id)
    )
    subject = subject_result.scalar_one_or_none()
    subject_code = subject.code if subject else ""

    # Try new prompts system first
    rubric_prompt_tpl = get_prompt(subject_code, "RUBRIC_GENERATION", "senior")

    if not rubric_prompt_tpl:
        # Fallback to legacy for subjects without new prompts
        from edu_cloud.modules.grading.prompts_legacy import build_rubric_generation_prompt
        from edu_cloud.modules.grading.llm_client import LLMClient

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
            return await client.generate_rubric(messages, images_b64=None)
        finally:
            await client.close()

    # New prompts path: build prompt with subject-specific template
    image_desc = ""
    question_section = f"【题目原文】\n{content or '(见图片)'}"
    answer_section = f"【参考答案】\n{reference_answer or '(见图片)'}"

    prompt_text = render_prompt(rubric_prompt_tpl, {
        "imageDescription": image_desc,
        "questionSection": question_section,
        "answerSection": answer_section,
        "fullScore": str(max_score),
    })

    # Collect images
    all_image_paths: list[str] = []
    if question.content_images:
        all_image_paths.extend(question.content_images)
    if question.reference_answer_images:
        all_image_paths.extend(question.reference_answer_images)

    upload_root = Path(settings.UPLOAD_DIR).resolve()
    parts: list = []
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
                parts.append(_make_image_part(local.read_bytes()))
            except OSError:
                logger.warning("generate_rubric_via_llm: cannot read image %s", local)

    parts.append(types.Part.from_text(text=prompt_text))
    contents = [types.Content(role="user", parts=parts)]

    # Call Gemini
    if settings.VERTEX_AI_PROJECT:
        client = GeminiClient(
            vertex_project=settings.VERTEX_AI_PROJECT,
            vertex_location=settings.VERTEX_AI_LOCATION,
            model=settings.GEMINI_MODEL or settings.LLM_MODEL,
            max_retries=settings.LLM_MAX_RETRIES,
        )
    else:
        client = GeminiClient(
            api_key=settings.GEMINI_API_KEY or settings.LLM_API_KEY,
            model=settings.GEMINI_MODEL or settings.LLM_MODEL,
            max_retries=settings.LLM_MAX_RETRIES,
        )
    raw = await client._generate(contents, method="rubric_gen", max_tokens=16384)
    parsed = extract_json(raw)

    if parsed and isinstance(parsed, dict) and "rubricItems" in parsed:
        return parsed["rubricItems"]
    elif parsed and isinstance(parsed, list):
        return parsed

    raise HTTPException(500, f"Failed to parse rubric generation response")


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
        return None
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

    # Both content and reference_answer empty (text + images) → 400
    has_text = bool((question.content or "").strip() or (question.reference_answer or "").strip())
    has_images = bool(question.content_images or question.reference_answer_images)
    if not has_text and not has_images:
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
    question_ids: list[str] | None = None
    limit: int | None = None
    mode: Literal["realtime", "batch"] = "realtime"
    use_vision: bool = False


def _task_response(t: GradingTask) -> dict:
    return {
        "id": t.id,
        "subject_id": t.subject_id,
        "question_id": t.question_id,
        "question_ids": t.question_ids,
        "status": t.status,
        "total": t.total,
        "completed": t.completed,
        "failed": t.failed,
        "grading_limit": t.grading_limit,
        "grading_mode": t.grading_mode,
        "created_by": t.created_by,
        "error_log": t.error_log,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


class GradeSingleRequest(BaseModel):
    answer_id: str
    use_vision: bool = False


@router.post("/grade-single")
async def grade_single_answer(
    req: GradeSingleRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
):
    """对单份答卷同步 AI 评分（用于质量抽检，preview-only）。

    复用 worker 的 OCR→评分 pipeline，但同步返回结果。
    不写入 GradingResult，仅返回预览数据，避免污染正式阅卷流程。
    """
    import json
    import base64
    import time as _time
    import aiofiles
    school_id = current["current_role"].school_id
    t_start = _time.perf_counter()
    plog = {"pipeline_type": "unknown", "is_blank": False}

    # 1. 查答卷
    answer = (await db.execute(
        select(StudentAnswer).where(
            StudentAnswer.id == req.answer_id,
            StudentAnswer.school_id == school_id,
        )
    )).scalar_one_or_none()
    if not answer:
        raise HTTPException(404, "答卷不存在")

    # 2. 查题目
    question = (await db.execute(
        select(Question).where(
            Question.id == answer.question_id,
            Question.school_id == school_id,
            Question.question_type.in_(QUESTION_TYPES_SUBJECTIVE),
        )
    )).scalar_one_or_none()
    if not question:
        raise HTTPException(400, "该题目不存在或非主观题")

    # 3. 查评分细则
    rubric = (await db.execute(
        select(Rubric).where(
            Rubric.question_id == question.id,
            Rubric.school_id == school_id,
        )
    )).scalar_one_or_none()
    if not rubric or not rubric.criteria:
        raise HTTPException(400, "请先为该题目配置评分细则")

    # 4. 查科目（获取 subject_code）+ 学科可见性校验
    subject = (await db.execute(
        select(Subject).where(
            Subject.id == question.subject_id,
            Subject.school_id == school_id,
        )
    )).scalar_one_or_none()
    subject_code = subject.code if subject else ""

    from edu_cloud.api.permissions import get_visible_subject_codes
    visible_codes = get_visible_subject_codes(current["current_role"])
    if visible_codes is not None and subject and subject.code not in visible_codes:
        raise HTTPException(403, "无权访问该科目")

    # 5. 读取答卷图片
    if not answer.image_path:
        raise HTTPException(400, "答卷无图片")
    try:
        async with aiofiles.open(answer.image_path, "rb") as f:
            image_data = await f.read()
        image_b64 = base64.b64encode(image_data).decode()
    except FileNotFoundError:
        raise HTTPException(404, "答卷图片文件不存在")

    plog["image_size_bytes"] = len(image_b64) * 3 // 4

    # 空白检测
    if len(image_b64) < 6800:
        plog["pipeline_type"] = "blank"
        plog["is_blank"] = True
        result_data = {
            "score": 0, "max_score": question.max_score,
            "feedback": "空白卷", "confidence": 1.0, "raw_content": "",
        }
    else:
        # 6. 创建 LLM 客户端（优先 Gemini 官方直连）
        from edu_cloud.workers.grading import _create_llm_client
        use_gemini = bool(settings.GEMINI_API_KEY or settings.VERTEX_AI_PROJECT)
        if use_gemini:
            llm = _create_llm_client(
                api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL,
                use_gemini_official=True,
            )
        else:
            from edu_cloud.modules.exam.slot_selector import get_llm_config, SLOT_AI_GRADING
            try:
                llm_url, llm_key, llm_model = await get_llm_config(
                    db, slot=SLOT_AI_GRADING, school_id=school_id,
                )
            except Exception:
                llm_url, llm_key, llm_model = None, None, None
            llm = _create_llm_client(api_url=llm_url, api_key=llm_key, model=llm_model)

        blanks = []
        try:
            from edu_cloud.modules.grading.prompts import get_prompt, render_prompt
            from edu_cloud.modules.grading.rubric_formatter import format_rubric_for_grading

            grading_prompt_tpl = get_prompt(subject_code, "GRADING_TEXT", "senior")
            ans_qtype = answer.question_type or question.question_type

            plog["grading_model"] = llm.model

            # Vision-direct for non-text question types
            _vision_tpl = get_prompt(subject_code, 'GRADING_VISION', 'senior') or get_prompt(subject_code, 'GRADING', 'senior')
            _use_vision = req.use_vision and _vision_tpl

            if _use_vision:
                plog["pipeline_type"] = "vision_direct"
                plog["grading_prompt_type"] = "GRADING_VISION"
                rubric_text = format_rubric_for_grading(rubric.criteria)
                _prompt = render_prompt(_vision_tpl, {
                    "fullScore": str(question.max_score),
                    "rubric": rubric_text,
                })
                t_grade = _time.perf_counter()
                grade_result = await llm.grade_vision(
                    images_b64=[image_b64],
                    prompt=_prompt,
                    max_score=question.max_score,
                )
                plog["grading_ms"] = int((_time.perf_counter() - t_grade) * 1000)
            elif grading_prompt_tpl is None:
                raise HTTPException(500, f"该科目（{subject_code}）缺少评分 prompt 配置，无法进行 AI 评分")
            else:
                # 两步：OCR → 文本评分
                plog["pipeline_type"] = "two_step"
                plog["ocr_model"] = llm.model
                rubric_text = format_rubric_for_grading(rubric.criteria)
                full_score = str(question.max_score)

                ocr_prompt = get_prompt(subject_code, "OCR_STRUCTURED", "senior") or get_prompt(subject_code, "OCR", "senior")
                plog["ocr_prompt_type"] = "OCR_STRUCTURED" if get_prompt(subject_code, "OCR_STRUCTURED", "senior") else "OCR"
                if ocr_prompt:
                    structure = "\n".join(f"- {c.get('blankNo', '?')}: {c.get('subQ', '')}" for c in rubric.criteria)
                    ocr_prompt = render_prompt(ocr_prompt, {"rubricStructure": structure})
                else:
                    from edu_cloud.modules.grading.prompts.base import OCR_PROMPT_BASE
                    ocr_prompt = OCR_PROMPT_BASE
                    plog["ocr_prompt_type"] = "OCR_BASE"

                t_ocr = _time.perf_counter()
                if use_gemini:
                    blanks = await llm.extract_text(image_bytes=image_data, prompt=ocr_prompt)
                else:
                    blanks = await llm.extract_text(images_b64=[image_b64], prompt=ocr_prompt)
                plog["ocr_ms"] = int((_time.perf_counter() - t_ocr) * 1000)

                from edu_cloud.modules.grading.ocr_validator import validate_ocr_blanks, recover_truncated_blanks
                blanks = validate_ocr_blanks(blanks)
                blanks = recover_truncated_blanks(blanks, len(rubric.criteria))

                extracted_text = "\n".join(f"{b.get('blankNo', '?')}: {b.get('text', '')}" for b in blanks)
                plog["ocr_text"] = extracted_text
                plog["ocr_blanks_count"] = len(blanks)

                # OCR-based blank detection: all blanks empty → 0 score
                non_empty = [b for b in blanks if b.get("text", "").strip()]
                if len(non_empty) == 0:
                    plog["pipeline_type"] = "blank"
                    plog["is_blank"] = True
                    plog["grading_ms"] = 0
                    result_data = {
                        "score": 0, "max_score": question.max_score,
                        "feedback": "空白卷（所有填空均未检测到作答内容）", "confidence": 1.0, "raw_content": "",
                        "details": [{"blankNo": b.get("blankNo", str(i+1)), "score": 0, "maxScore": 0, "reason": "未作答"} for i, b in enumerate(blanks)],
                    }
                else:
                    char_stats = ""
                    if ans_qtype == "essay":
                        from edu_cloud.modules.grading.prompts.base import count_essay_chars
                        raw_text = "".join(b.get("text", "") for b in blanks)
                        char_count, char_stats = count_essay_chars(raw_text)
                        plog["char_count"] = char_count

                    plog["grading_prompt_type"] = "GRADING_TEXT"
                    grading_prompt = render_prompt(grading_prompt_tpl, {
                        "fullScore": full_score,
                        "rubric": rubric_text,
                        "extractedText": extracted_text,
                        "charStats": char_stats,
                    })
                    t_grade = _time.perf_counter()
                    grade_result = await llm.grade_text(prompt=grading_prompt, max_score=question.max_score)
                    plog["grading_ms"] = int((_time.perf_counter() - t_grade) * 1000)
                    result_data = {
                        "score": grade_result.score,
                        "max_score": grade_result.max_score,
                        "feedback": grade_result.feedback,
                        "confidence": grade_result.confidence,
                        "raw_content": grade_result.raw_content,
                        "details": grade_result.details,
                        "deductions": grade_result.deductions,
                        "comment": grade_result.comment,
                    }
            plog["score"] = grade_result.score
            plog["confidence"] = grade_result.confidence
        except Exception as e:
            logger.error("grade_single: answer=%s failed: %s", req.answer_id, e, exc_info=True)
            plog["error_type"] = type(e).__name__
            plog["error_message"] = str(e)
            raise HTTPException(500, "AI 评分失败，请稍后重试")
        finally:
            await llm.close()

    plog["total_ms"] = int((_time.perf_counter() - t_start) * 1000)

    # 7. 写入 pipeline log
    from edu_cloud.modules.grading.models import GradingPipelineLog
    db.add(GradingPipelineLog(
        answer_id=req.answer_id,
        question_id=question.id,
        school_id=school_id,
        subject_code=subject_code,
        question_type=answer.question_type or question.question_type,
        pipeline_type=plog.get("pipeline_type", "unknown"),
        image_size_bytes=plog.get("image_size_bytes"),
        is_blank=plog.get("is_blank", False),
        ocr_model=plog.get("ocr_model"),
        ocr_prompt_type=plog.get("ocr_prompt_type"),
        ocr_ms=plog.get("ocr_ms"),
        ocr_text=plog.get("ocr_text"),
        ocr_blanks_count=plog.get("ocr_blanks_count"),
        char_count=plog.get("char_count"),
        grading_model=plog.get("grading_model"),
        grading_prompt_type=plog.get("grading_prompt_type"),
        grading_ms=plog.get("grading_ms"),
        total_ms=plog.get("total_ms"),
        score=plog.get("score"),
        confidence=plog.get("confidence"),
        error_type=plog.get("error_type"),
        error_message=plog.get("error_message"),
    ))

    # 8. 构建完整结果（details 已在 grade_text 中 flatten）
    details = result_data.get("details") or []
    deductions = result_data.get("deductions") or []
    comment = result_data.get("comment", "")
    recognized_text = plog.get("ocr_text")

    feedback = comment or result_data.get("feedback", "")

    logger.info("grade_single: answer=%s, score=%.1f (preview only, no DB write)",
                req.answer_id, result_data["score"])

    return {
        "score": result_data["score"],
        "max_score": result_data["max_score"],
        "feedback": feedback,
        "confidence": result_data["confidence"],
        "details": details,
        "deductions": deductions,
        "comment": comment,
        "recognizedText": recognized_text,
    }


async def enqueue_grading_task(task_id: str) -> None:
    """Enqueue an arq job. Separated for testability (mock in tests)."""
    from arq import create_pool
    from arq.connections import RedisSettings
    from edu_cloud.config import settings
    from edu_cloud.logging_config import get_trace_context
    trace_ctx = get_trace_context()
    redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    try:
        await redis.enqueue_job("process_grading_task", task_id, _trace_ctx=trace_ctx)
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
    confirmed_count = 0

    if req.question_id and req.question_ids:
        raise HTTPException(400, "question_id 和 question_ids 不能同时指定")

    # 前置校验 1：Subject 归属
    result = await db.execute(
        select(Subject).where(
            Subject.id == req.subject_id,
            Subject.school_id == school_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Subject not found")

    if req.question_ids:
        # --- Multi-question batch path ---
        q_rows = (await db.execute(
            select(Question).where(
                Question.id.in_(req.question_ids),
                Question.subject_id == req.subject_id,
                Question.school_id == school_id,
                Question.question_type.in_(QUESTION_TYPES_SUBJECTIVE),
            )
        )).scalars().all()
        found_ids = {q.id for q in q_rows}
        missing = set(req.question_ids) - found_ids
        if missing:
            raise HTTPException(400, f"以下题目不存在、不属于该科目或非主观题: {missing}")

        rubric_count = (await db.execute(
            select(func.count(Rubric.id)).where(
                Rubric.question_id.in_(req.question_ids),
                Rubric.school_id == school_id,
            )
        )).scalar() or 0
        if rubric_count < len(req.question_ids):
            raise HTTPException(400, "部分题目未配置评分标准（Rubric），请先为所有选中题目生成细则")

        answer_count = (await db.execute(
            select(func.count(StudentAnswer.id)).where(
                StudentAnswer.subject_id == req.subject_id,
                StudentAnswer.school_id == school_id,
                StudentAnswer.question_id.in_(req.question_ids),
            )
        )).scalar() or 0
        if answer_count == 0:
            raise HTTPException(400, "选中题目暂无可批改答卷")

        old_results = (await db.execute(
            select(GradingResult).where(
                GradingResult.question_id.in_(req.question_ids),
                GradingResult.school_id == school_id,
                GradingResult.status == "ai_pending",
            )
        )).scalars().all()
        for old in old_results:
            await db.delete(old)
        if old_results:
            await db.commit()
            logger.info("create_grading_task: cleaned %d stale ai_pending for batch questions", len(old_results))

        confirmed_count = (await db.execute(
            select(func.count(GradingResult.id)).where(
                GradingResult.question_id.in_(req.question_ids),
                GradingResult.school_id == school_id,
                GradingResult.status == "confirmed",
            )
        )).scalar() or 0

    elif req.question_id:
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

        # AGP-004: Clean stale in-progress results only; preserve ai_done (incremental grading)
        old_results = (await db.execute(
            select(GradingResult).where(
                GradingResult.question_id == req.question_id,
                GradingResult.school_id == school_id,
                GradingResult.status == "ai_pending",
            )
        )).scalars().all()
        for old in old_results:
            await db.delete(old)
        if old_results:
            await db.commit()
            logger.info("create_grading_task: cleaned %d stale ai_pending results for question=%s",
                        len(old_results), req.question_id)

        confirmed_count = (await db.execute(
            select(func.count(GradingResult.id)).where(
                GradingResult.question_id == req.question_id,
                GradingResult.school_id == school_id,
                GradingResult.status == "confirmed",
            )
        )).scalar() or 0

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

        # Subject-level: clean stale ai_pending only; preserve ai_done
        old_results = (await db.execute(
            select(GradingResult).where(
                GradingResult.question_id.in_(subjective_q_ids),
                GradingResult.school_id == school_id,
                GradingResult.status == "ai_pending",
            )
        )).scalars().all()
        for old in old_results:
            await db.delete(old)
        if old_results:
            await db.commit()
            logger.info("create_grading_task: cleaned %d stale ai_pending subject-level results", len(old_results))

        confirmed_count = (await db.execute(
            select(func.count(GradingResult.id)).where(
                GradingResult.question_id.in_(subjective_q_ids),
                GradingResult.school_id == school_id,
                GradingResult.status == "confirmed",
            )
        )).scalar() or 0

    # 并发防护：同题/同科目不允许重叠的 pending/processing 任务
    overlap_filter = [
        GradingTask.school_id == school_id,
        GradingTask.subject_id == req.subject_id,
        GradingTask.status.in_(["pending", "processing"]),
    ]
    if req.question_id:
        overlap_filter.append(GradingTask.question_id == req.question_id)
    elif req.question_ids:
        import json as _json
        running_tasks = (await db.execute(
            select(GradingTask).where(*overlap_filter, GradingTask.question_ids != None)
        )).scalars().all()
        req_set = set(req.question_ids)
        existing = 0
        for rt in running_tasks:
            try:
                rt_ids = set(_json.loads(rt.question_ids)) if isinstance(rt.question_ids, str) else set(rt.question_ids)
            except Exception:
                rt_ids = set()
            if req_set & rt_ids:
                existing = 1
                break
    else:
        overlap_filter.append(GradingTask.question_id == None)
        overlap_filter.append(GradingTask.question_ids == None)
    if not req.question_ids:
        existing = (await db.execute(
            select(func.count(GradingTask.id)).where(*overlap_filter)
        )).scalar() or 0
    if existing:
        raise HTTPException(409, "该题目/科目已有正在运行的阅卷任务，请等待完成后再启动")

    # 创建 task（commit 以获得 ID），后续 enqueue 失败则清理 orphan
    task = GradingTask(
        subject_id=req.subject_id,
        question_id=req.question_id,
        question_ids=req.question_ids,
        school_id=school_id,
        status="pending",
        total=0,
        completed=0,
        failed=0,
        grading_limit=req.limit,
        grading_mode=req.mode,
        use_vision=req.use_vision,
        created_by=current["user"].id,
    )
    db.add(task)

    # 自动为子题创建 Vision task（父题走两步，子题走 Vision 直评）
    child_tasks = []
    if req.question_id:
        child_questions = (await db.execute(
            select(Question).where(
                Question.parent_id == req.question_id,
                Question.school_id == school_id,
            )
        )).scalars().all()
        for cq in child_questions:
            # 清理子题 ai_pending（保留 ai_done）
            old_child = (await db.execute(
                select(GradingResult).where(
                    GradingResult.question_id == cq.id,
                    GradingResult.school_id == school_id,
                    GradingResult.status == "ai_pending",
                )
            )).scalars().all()
            for old in old_child:
                await db.delete(old)

            ct = GradingTask(
                subject_id=req.subject_id,
                question_id=cq.id,
                school_id=school_id,
                status="pending",
                total=0, completed=0, failed=0,
                grading_limit=req.limit,
                grading_mode=req.mode,
                use_vision=True,
                created_by=current["user"].id,
            )
            db.add(ct)
            child_tasks.append(ct)
            logger.info("create_grading_task: auto child task for question=%s (vision=true)", cq.name)

    await db.commit()
    await db.refresh(task)
    for ct in child_tasks:
        await db.refresh(ct)

    logger.info("create_grading_task: id=%s, subject=%s, children=%d, created_by=%s",
                task.id, req.subject_id, len(child_tasks), current["user"].username)
    business_event("task_create", "grading_task", task.id, exam_id=req.subject_id)

    # F007 orphan 防御：enqueue 失败必须清理已落库的 GradingTask
    all_tasks = [task] + child_tasks
    try:
        for t in all_tasks:
            await enqueue_grading_task(t.id)
    except Exception as e:
        logger.error(
            "create_grading_task: enqueue failed, cleaning up %d orphan tasks, error=%s",
            len(all_tasks), e, exc_info=True,
        )
        for t in all_tasks:
            await db.delete(t)
        await db.commit()
        raise HTTPException(503, f"任务队列暂不可用，请稍后重试: {e}")

    resp = _task_response(task)
    if child_tasks:
        resp["child_task_ids"] = [str(ct.id) for ct in child_tasks]
    if confirmed_count > 0:
        resp["warning"] = f"{confirmed_count} 份答卷已有人工确认评分，AI 将跳过这些答卷"
        resp["confirmed_skipped"] = confirmed_count
    return resp


@router.get("/tasks")
async def list_grading_tasks(
    subject_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    from edu_cloud.api.permissions import get_visible_subject_codes

    school_id = current["current_role"].school_id
    q = select(GradingTask)
    if school_id:
        q = q.where(GradingTask.school_id == school_id)
    if subject_id:
        q = q.where(GradingTask.subject_id == subject_id)

    # L2: filter by visible subject codes
    visible_subjects = get_visible_subject_codes(current["current_role"])
    if visible_subjects is not None:
        q = (
            q.join(Subject, GradingTask.subject_id == Subject.id)
            .where(Subject.code.in_(visible_subjects))
        )

    result = await db.execute(q.order_by(GradingTask.created_at.desc()))
    return [_task_response(t) for t in result.scalars().all()]


@router.post("/tasks/{task_id}/cancel")
async def cancel_grading_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),
):
    school_id = current["current_role"].school_id
    filters = [GradingTask.id == task_id]
    if school_id:
        filters.append(GradingTask.school_id == school_id)
    result = await db.execute(select(GradingTask).where(*filters))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")
    if task.status in ("completed", "cancelled", "failed"):
        return {"status": task.status, "message": "Task already finished"}
    task.status = "cancelled"
    await db.commit()
    return {"status": "cancelled", "message": "Task cancelled"}


@router.get("/tasks/{task_id}")
async def get_grading_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    from edu_cloud.api.permissions import get_visible_subject_codes

    school_id = current["current_role"].school_id
    filters = [GradingTask.id == task_id]
    if school_id:
        filters.append(GradingTask.school_id == school_id)
    result = await db.execute(select(GradingTask).where(*filters))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")

    # L2: verify task's subject is within visible scope
    visible_subjects = get_visible_subject_codes(current["current_role"])
    if visible_subjects is not None:
        subject = (await db.execute(
            select(Subject).where(
                Subject.id == task.subject_id,
                Subject.school_id == school_id,
            )
        )).scalar_one_or_none()
        if not subject or subject.code not in visible_subjects:
            raise HTTPException(403, "No access to this subject")

    return _task_response(task)


