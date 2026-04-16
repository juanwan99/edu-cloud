"""AI 阅卷 Worker — 后台处理主观题评分任务。

通过 arq 调度，从 Redis 接收 task_id，微批次并发调用 LLM 评分。
"""
import asyncio
import base64
import logging
import time
import aiofiles

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from edu_cloud.config import settings
from edu_cloud.modules.exam.models import Question, QUESTION_TYPES_SUBJECTIVE
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import Rubric, GradingTask, GradingResult

logger = logging.getLogger(__name__)


def _create_llm_client():
    """Create LLM client for grading (reads from settings)."""
    from edu_cloud.modules.grading.llm_client import LLMClient
    return LLMClient(
        api_url=settings.LLM_API_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        timeout=settings.LLM_TIMEOUT,
        max_retries=settings.LLM_MAX_RETRIES,
    )


async def _read_image_b64(path: str) -> str:
    async with aiofiles.open(path, "rb") as f:
        data = await f.read()
    return base64.b64encode(data).decode()


async def _grade_single(
    llm,
    ad: dict,
    rubrics_by_question: dict,
) -> tuple[dict | None, dict | None]:
    """Grade a single answer. Returns (result_dict, error_dict).

    Exactly one of the two is non-None.
    """
    answer_id = ad["answer_id"]
    question_id = ad["question_id"]

    rubric_criteria = rubrics_by_question.get(question_id)
    if rubric_criteria is None:
        logger.warning("grading_task: no rubric for question=%s", question_id)
        return None, {"answer_id": answer_id, "error": f"No rubric for question {question_id}"}

    try:
        image_b64 = await _read_image_b64(ad["image_path"])
        grade_result = await llm.grade(
            image_b64=image_b64,
            rubric={"criteria": rubric_criteria},
            question={"name": ad["question_name"], "max_score": ad["question_max_score"]},
            question_type=ad.get("question_type"),
        )
        return {
            "answer_id": answer_id,
            "question_id": question_id,
            "score": grade_result.score,
            "max_score": grade_result.max_score,
            "feedback": grade_result.feedback,
            "confidence": grade_result.confidence,
            "raw_content": grade_result.raw_content,
        }, None
    except (ValueError, KeyError, TypeError, RuntimeError) as e:
        logger.warning("grading_task: answer=%s FAILED: %s", answer_id, e)
        return None, {"answer_id": answer_id, "error": str(e)}


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
    llm = _create_llm_client()
    try:
        async with session_factory() as db:
            # Load task
            result = await db.execute(select(GradingTask).where(GradingTask.id == task_id))
            task = result.scalar_one()
            task.status = "processing"
            await db.commit()
            logger.info("grading_task: task=%s, subject=%s, status→processing", task_id, task.subject_id)

            # Find subjective questions
            q_result = await db.execute(
                select(Question).where(
                    Question.subject_id == task.subject_id,
                    Question.school_id == task.school_id,
                    Question.question_type.in_(QUESTION_TYPES_SUBJECTIVE),
                )
            )
            questions = {q.id: q for q in q_result.scalars().all()}
            logger.info("grading_task: task=%s, subjective_questions=%d", task_id, len(questions))

            if not questions:
                task.status = "completed"
                await db.commit()
                logger.info("grading_task DONE: task=%s, no subjective questions", task_id)
                return

            # Find all answers
            a_result = await db.execute(
                select(StudentAnswer).where(
                    StudentAnswer.subject_id == task.subject_id,
                    StudentAnswer.school_id == task.school_id,
                    StudentAnswer.question_id.in_(list(questions.keys())),
                )
            )
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
                })

            # Load rubrics
            rubric_result = await db.execute(
                select(Rubric).where(Rubric.question_id.in_(list(questions.keys())))
            )
            rubrics_by_question = {r.question_id: r.criteria for r in rubric_result.scalars().all()}

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
                coros = [_grade_single(llm, ad, rubrics_by_question) for ad in batch]
                batch_results = await asyncio.gather(*coros)

                # Write results to DB (sequential DB writes within each batch)
                batch_completed = 0
                batch_failed = 0
                for result_dict, error_dict in batch_results:
                    if error_dict is not None:
                        errors.append(error_dict)
                        batch_failed += 1
                    else:
                        gr = GradingResult(
                            ai_task_id=task.id,
                            answer_id=result_dict["answer_id"],
                            question_id=result_dict["question_id"],
                            school_id=task.school_id,
                            ai_score=result_dict["score"],
                            ai_confidence=result_dict["confidence"],
                            ai_feedback=result_dict["feedback"],
                            ai_raw_response={"raw_content": result_dict["raw_content"]},
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
