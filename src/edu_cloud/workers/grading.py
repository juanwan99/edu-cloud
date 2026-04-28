"""AI 阅卷 Worker — 后台处理主观题评分任务。

通过 arq 调度，从 Redis 接收 task_id，微批次并发调用 LLM 评分。
"""
import asyncio
import base64
import json
import logging
import time
import aiofiles

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from edu_cloud.config import settings
from edu_cloud.modules.exam.models import Question, Subject, QUESTION_TYPES_SUBJECTIVE
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import Rubric, GradingTask, GradingResult
import edu_cloud.models.user  # noqa: F401 — FK resolution for grading_tasks.created_by
import edu_cloud.models.school  # noqa: F401 — FK resolution for *.school_id

logger = logging.getLogger(__name__)


def _create_llm_client(
    api_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> "LLMClient":
    """Create LLM client for grading.

    When called with DB-resolved values, those override .env settings.
    When called without arguments, falls back to .env settings entirely.
    """
    from edu_cloud.modules.grading.llm_client import LLMClient
    return LLMClient(
        api_url=api_url or settings.LLM_API_URL,
        api_key=api_key or settings.LLM_API_KEY,
        model=model or settings.LLM_MODEL,
        timeout=settings.LLM_TIMEOUT,
        max_retries=settings.LLM_MAX_RETRIES,
        slot=settings.LLM_SLOT,
    )


async def _read_image_b64(path: str) -> str:
    async with aiofiles.open(path, "rb") as f:
        data = await f.read()
    return base64.b64encode(data).decode()


_grading_semaphore = asyncio.Semaphore(20)


async def _grade_single(
    llm,
    ad: dict,
    rubrics_by_question: dict,
) -> tuple[dict | None, dict | None, dict]:
    """Grade a single answer using two-step pipeline: OCR -> text-based grading.

    Falls back to legacy single-step if subject prompts not available.
    Returns (result_dict, error_dict, pipeline_log_dict).
    """
    answer_id = ad["answer_id"]
    question_id = ad["question_id"]
    t_start = time.perf_counter()

    plog = {
        "answer_id": answer_id,
        "question_id": question_id,
        "subject_code": ad.get("subject_code", ""),
        "question_type": ad.get("question_type", ""),
        "pipeline_type": "unknown",
        "is_blank": False,
        "image_size_bytes": None,
        "ocr_model": None, "ocr_prompt_type": None, "ocr_ms": None,
        "ocr_text": None, "ocr_blanks_count": None, "char_count": None,
        "grading_model": None, "grading_prompt_type": None, "grading_ms": None,
        "total_ms": None, "score": None, "confidence": None,
        "error_type": None, "error_message": None,
    }

    rubric_criteria = rubrics_by_question.get(question_id)
    if rubric_criteria is None:
        logger.warning("grading_task: no rubric for question=%s", question_id)
        plog["pipeline_type"] = "error"
        plog["error_type"] = "no_rubric"
        plog["error_message"] = f"No rubric for question {question_id}"
        plog["total_ms"] = int((time.perf_counter() - t_start) * 1000)
        return None, {"answer_id": answer_id, "error": plog["error_message"]}, plog

    try:
        image_b64 = await _read_image_b64(ad["image_path"])
        plog["image_size_bytes"] = len(image_b64) * 3 // 4

        # Blank detection
        if len(image_b64) < 6800:
            plog["pipeline_type"] = "blank"
            plog["is_blank"] = True
            plog["score"] = 0
            plog["confidence"] = 1.0
            plog["total_ms"] = int((time.perf_counter() - t_start) * 1000)
            return {
                "answer_id": answer_id, "question_id": question_id,
                "score": 0, "max_score": ad["question_max_score"],
                "feedback": "空白卷", "confidence": 1.0, "raw_content": "",
            }, None, plog

        subject = ad.get("subject_code", "")
        from edu_cloud.modules.grading.prompts import get_prompt, render_prompt

        grading_prompt_tpl = get_prompt(subject, "GRADING_TEXT", "senior")
        if grading_prompt_tpl is None:
            plog["pipeline_type"] = "error"
            plog["error_type"] = "no_prompt"
            plog["error_message"] = f"No grading prompt for subject '{subject}'"
            plog["total_ms"] = int((time.perf_counter() - t_start) * 1000)
            logger.error("grading_task: no prompt for subject=%s, answer=%s — legacy pipeline disabled", subject, answer_id)
            return None, {"answer_id": answer_id, "error": plog["error_message"]}, plog

        # Two-step path
        plog["pipeline_type"] = "two_step"
        plog["ocr_model"] = llm.model
        plog["grading_model"] = llm.model
        from edu_cloud.modules.grading.rubric_formatter import format_rubric_for_grading

        rubric_text = format_rubric_for_grading(rubric_criteria)
        full_score = str(ad["question_max_score"])

        # Step 1: OCR
        ocr_prompt = get_prompt(subject, "OCR_STRUCTURED", "senior") or get_prompt(subject, "OCR", "senior")
        plog["ocr_prompt_type"] = "OCR_STRUCTURED" if get_prompt(subject, "OCR_STRUCTURED", "senior") else "OCR"
        if ocr_prompt:
            structure = "\n".join(f"- {c.get('blankNo', '?')}: {c.get('subQ', '')}" for c in rubric_criteria)
            ocr_prompt = render_prompt(ocr_prompt, {"rubricStructure": structure})
        else:
            from edu_cloud.modules.grading.prompts.base import OCR_PROMPT_BASE
            ocr_prompt = OCR_PROMPT_BASE
            plog["ocr_prompt_type"] = "OCR_BASE"

        t_ocr = time.perf_counter()
        blanks = await llm.extract_text(images_b64=[image_b64], prompt=ocr_prompt)
        plog["ocr_ms"] = int((time.perf_counter() - t_ocr) * 1000)

        from edu_cloud.modules.grading.ocr_validator import validate_ocr_blanks, recover_truncated_blanks
        blanks = validate_ocr_blanks(blanks)
        blanks = recover_truncated_blanks(blanks, len(rubric_criteria))

        extracted_text = "\n".join(f"{b.get('blankNo', '?')}: {b.get('text', '')}" for b in blanks)
        plog["ocr_text"] = extracted_text
        plog["ocr_blanks_count"] = len(blanks)

        # OCR-based blank detection: check each blank individually
        non_empty_blanks = [b for b in blanks if b.get("text", "").strip()]
        if len(non_empty_blanks) == 0:
            plog["pipeline_type"] = "blank"
            plog["is_blank"] = True
            plog["score"] = 0
            plog["confidence"] = 1.0
            plog["total_ms"] = int((time.perf_counter() - t_start) * 1000)
            logger.info("grading_task: OCR blank detection — all %d blanks empty, answer=%s", len(blanks), answer_id)
            return {
                "answer_id": answer_id, "question_id": question_id,
                "score": 0, "max_score": ad["question_max_score"],
                "feedback": "空白卷（所有填空均未检测到作答内容）", "confidence": 1.0, "raw_content": "",
                "details": [{"blankNo": b.get("blankNo", str(i+1)), "score": 0, "maxScore": 0, "reason": "未作答"} for i, b in enumerate(blanks)],
            }, None, plog

        # Character count for essay questions
        char_stats = ""
        if ad.get("question_type") == "essay":
            import re
            raw_text = "".join(b.get("text", "") for b in blanks)
            cn_chars = len(re.findall(r'[一-鿿]', raw_text))
            en_words = len(re.findall(r'[a-zA-Z]+', raw_text))
            plog["char_count"] = cn_chars if cn_chars > en_words else en_words
            if cn_chars > en_words:
                char_stats = f"【字数统计】{cn_chars}字（基于OCR精确统计，请据此判断是否达到字数要求）"
            else:
                char_stats = f"【字数统计】{en_words}词（基于OCR精确统计，请据此判断是否达到词数要求）"

        # Step 2: Grade text
        plog["grading_prompt_type"] = "GRADING_TEXT"
        grading_prompt = render_prompt(grading_prompt_tpl, {
            "fullScore": full_score,
            "rubric": rubric_text,
            "extractedText": extracted_text,
            "charStats": char_stats,
        })

        t_grade = time.perf_counter()
        grade_result = await llm.grade_text(prompt=grading_prompt, max_score=ad["question_max_score"])
        plog["grading_ms"] = int((time.perf_counter() - t_grade) * 1000)
        plog["score"] = grade_result.score
        plog["confidence"] = grade_result.confidence
        plog["total_ms"] = int((time.perf_counter() - t_start) * 1000)

        return {
            "answer_id": answer_id, "question_id": question_id,
            "score": grade_result.score, "max_score": grade_result.max_score,
            "feedback": grade_result.feedback, "confidence": grade_result.confidence,
            "raw_content": grade_result.raw_content,
            "recognizedText": extracted_text,
            "ocr_blanks": blanks,
        }, None, plog

    except (ValueError, KeyError, TypeError, RuntimeError) as e:
        logger.warning("grading_task: answer=%s FAILED: %s", answer_id, e)
        plog["pipeline_type"] = plog["pipeline_type"] if plog["pipeline_type"] != "unknown" else "error"
        plog["error_type"] = type(e).__name__
        plog["error_message"] = str(e)
        plog["total_ms"] = int((time.perf_counter() - t_start) * 1000)
        return None, {"answer_id": answer_id, "error": str(e)}, plog


async def _grade_with_semaphore(llm, ad, rubrics):
    async with _grading_semaphore:
        return await _grade_single(llm, ad, rubrics)


async def process_grading_task(ctx: dict, task_id: str) -> None:
    """Process a single grading task: load answers, call LLM in micro-batches, save results."""
    task_start = time.perf_counter()
    logger.info("grading_task START: task=%s", task_id)

    session_factory = ctx.get("db_session_factory")

    local_engine = None
    if session_factory is None or not isinstance(session_factory, async_sessionmaker):
        local_engine = create_async_engine(settings.DATABASE_URL)
        session_factory = async_sessionmaker(local_engine, class_=AsyncSession, expire_on_commit=False)

    batch_size = settings.GRADING_BATCH_SIZE
    llm = None
    try:
        async with session_factory() as db:
            # Load task
            result = await db.execute(select(GradingTask).where(GradingTask.id == task_id))
            task = result.scalar_one()
            task.status = "processing"
            await db.commit()
            logger.info("grading_task: task=%s, subject=%s, status→processing", task_id, task.subject_id)

            # Resolve LLM config: school override → platform default → .env fallback
            from edu_cloud.modules.exam.slot_selector import get_llm_config, SLOT_AI_GRADING
            try:
                llm_url, llm_key, llm_model = await get_llm_config(
                    db, slot=SLOT_AI_GRADING, school_id=task.school_id,
                )
                logger.info("grading_task: task=%s, llm_config resolved from DB (model=%s)", task_id, llm_model)
            except Exception:
                llm_url, llm_key, llm_model = None, None, None
                logger.warning("grading_task: task=%s, llm_config DB lookup failed, fallback to .env", task_id, exc_info=True)

            llm = _create_llm_client(api_url=llm_url, api_key=llm_key, model=llm_model)

            # Find subjective questions
            if task.question_id:
                # Question-level: only load specified question
                q_result = await db.execute(
                    select(Question).where(
                        Question.id == task.question_id,
                        Question.subject_id == task.subject_id,
                        Question.school_id == task.school_id,
                        Question.question_type.in_(QUESTION_TYPES_SUBJECTIVE),
                    )
                )
            else:
                # Subject-level: load all subjective questions (ORC-002: unchanged)
                q_result = await db.execute(
                    select(Question).where(
                        Question.subject_id == task.subject_id,
                        Question.school_id == task.school_id,
                        Question.question_type.in_(QUESTION_TYPES_SUBJECTIVE),
                    )
                )
            questions = {q.id: q for q in q_result.scalars().all()}
            logger.info("grading_task: task=%s, question_id=%s, subjective_questions=%d",
                        task_id, task.question_id, len(questions))

            # Get subject code for prompt dispatch
            subject_result = await db.execute(select(Subject).where(Subject.id == task.subject_id))
            subject_row = subject_result.scalar_one_or_none()
            subject_code = subject_row.code if subject_row else ""

            if not questions:
                task.status = "completed"
                await db.commit()
                logger.info("grading_task DONE: task=%s, no subjective questions", task_id)
                return

            # Find answers — filter by question scope
            answer_filter = [
                StudentAnswer.subject_id == task.subject_id,
                StudentAnswer.school_id == task.school_id,
                StudentAnswer.question_id.in_(list(questions.keys())),
            ]
            if task.question_id:
                answer_filter.append(StudentAnswer.question_id == task.question_id)
            a_result = await db.execute(select(StudentAnswer).where(*answer_filter))
            answers_raw = a_result.scalars().all()

            answer_data = []
            for a in answers_raw:
                q = questions[a.question_id]
                # Phase 1-C: 优先用 paper-seg 上传时携带的 question_type，
                # 缺省回退到 Question.question_type
                ans_qtype = a.question_type or q.question_type
                answer_data.append({
                    "answer_id": a.id,
                    "question_id": q.id,
                    "question_name": q.name,
                    "question_max_score": q.max_score,
                    "image_path": a.image_path,
                    "question_type": ans_qtype,
                    "subject_code": subject_code,
                })

            # Exclude answers that already have confirmed results (ORC-001 protection)
            if answer_data:
                confirmed_rows = (await db.execute(
                    select(GradingResult.answer_id).where(
                        GradingResult.answer_id.in_([a["answer_id"] for a in answer_data]),
                        GradingResult.status == "confirmed",
                    )
                )).scalars().all()
                confirmed_set = set(confirmed_rows)
                if confirmed_set:
                    answer_data = [a for a in answer_data if a["answer_id"] not in confirmed_set]
                    logger.info("grading_task: excluded %d confirmed answers", len(confirmed_set))

            # Load rubrics
            rubric_result = await db.execute(
                select(Rubric).where(Rubric.question_id.in_(list(questions.keys())))
            )
            rubrics_by_question = {r.question_id: r.criteria for r in rubric_result.scalars().all()}

            if task.grading_limit and task.grading_limit > 0 and len(answer_data) > task.grading_limit:
                logger.info("grading_task: applying limit %d (total available %d)", task.grading_limit, len(answer_data))
                answer_data = answer_data[:task.grading_limit]

            task.total = len(answer_data)
            await db.commit()
            logger.info("grading_task: task=%s, answers=%d, rubrics=%d, batch_size=%d",
                        task_id, len(answer_data), len(rubrics_by_question), batch_size)

            # Process in micro-batches
            errors = []
            processed = 0
            for batch_start in range(0, len(answer_data), batch_size):
                batch = answer_data[batch_start:batch_start + batch_size]
                batch_num = batch_start // batch_size + 1
                logger.info("grading_task: task=%s, batch %d, size=%d", task_id, batch_num, len(batch))

                # Launch all LLM calls in this batch concurrently
                coros = [_grade_with_semaphore(llm, ad, rubrics_by_question) for ad in batch]
                batch_results = await asyncio.gather(*coros)

                # Write results + pipeline logs to DB
                from edu_cloud.modules.grading.models import GradingPipelineLog
                batch_completed = 0
                batch_failed = 0
                for result_dict, error_dict, plog in batch_results:
                    # Always write pipeline log
                    db.add(GradingPipelineLog(
                        answer_id=plog["answer_id"],
                        question_id=plog["question_id"],
                        task_id=task.id,
                        school_id=task.school_id,
                        subject_code=plog.get("subject_code"),
                        question_type=plog.get("question_type"),
                        pipeline_type=plog["pipeline_type"],
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

                    if error_dict is not None:
                        errors.append(error_dict)
                        batch_failed += 1
                    else:
                        details = result_dict.get("details")
                        if details is None:
                            try:
                                raw_parsed = json.loads(result_dict["raw_content"])
                                details = raw_parsed.get("details")
                            except (json.JSONDecodeError, TypeError):
                                pass

                        ocr_blanks = result_dict.get("ocr_blanks") or []
                        ocr_by_no = {str(b.get("blankNo", "")): b.get("text", "") for b in ocr_blanks}
                        if details and isinstance(details, list):
                            for d in details:
                                bno = str(d.get("blankNo", ""))
                                if bno in ocr_by_no:
                                    d["answer"] = ocr_by_no[bno]
                                d["correct"] = d.get("score", 0) >= d.get("maxScore", 1)

                        gr = GradingResult(
                            ai_task_id=task.id,
                            answer_id=result_dict["answer_id"],
                            question_id=result_dict["question_id"],
                            school_id=task.school_id,
                            ai_score=result_dict["score"],
                            ai_confidence=result_dict["confidence"],
                            ai_feedback=result_dict["feedback"],
                            ai_raw_response={
                                "raw_content": result_dict["raw_content"],
                                "details": details,
                                "recognizedText": result_dict.get("recognizedText"),
                            },
                            final_score=result_dict["score"],
                            max_score=result_dict["max_score"],
                            status="ai_done",
                        )
                        db.add(gr)
                        batch_completed += 1

                # Update progress after each batch
                processed += len(batch)
                result = await db.execute(select(GradingTask).where(GradingTask.id == task_id))
                task = result.scalar_one()
                task.completed += batch_completed
                task.failed += batch_failed
                await db.commit()
                logger.info("grading_task: task=%s, batch %d done, +%d completed, +%d failed, progress=%d/%d",
                            task_id, batch_num, batch_completed, batch_failed, processed, len(answer_data))

            # Final status
            result = await db.execute(select(GradingTask).where(GradingTask.id == task_id))
            task = result.scalar_one()
            task.status = "failed" if errors else "completed"
            task.error_log = errors if errors else None
            await db.commit()

            elapsed = time.perf_counter() - task_start
            logger.info("grading_task DONE: task=%s, status=%s, completed=%d, failed=%d, elapsed=%.1fs",
                        task_id, task.status, task.completed, task.failed, elapsed)
    finally:
        if llm is not None:
            await llm.close()
        if local_engine is not None:
            await local_engine.dispose()


async def run_post_exam_pipeline(ctx: dict, exam_id: str, school_id: str) -> None:
    """考后流水线 arq 任务 — 调用 pipeline 全流程。"""
    logger.info("post_exam_pipeline START: exam=%s, school=%s", exam_id, school_id)
    from edu_cloud.database import async_session
    from edu_cloud.modules.pipeline.service import run_full_pipeline
    async with async_session() as db:
        results = await run_full_pipeline(db, exam_id=exam_id, school_id=school_id)
        await db.commit()
    logger.info("post_exam_pipeline DONE: exam=%s, results=%s", exam_id, results)
