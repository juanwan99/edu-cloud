"""AI 阅卷 Worker — 后台处理主观题评分任务。

通过 arq 调度，从 Redis 接收 task_id，批量调用 LLM 评分。
"""
import base64
import logging
import time
import aiofiles

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from edu_cloud.config import settings
from edu_cloud.modules.exam.models import Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import Rubric, GradingTask, AIGradingResult

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


async def process_grading_task(ctx: dict, task_id: str) -> None:
    """Process a single grading task: load answers, call LLM, save results."""
    task_start = time.perf_counter()
    logger.info("grading_task START: task=%s", task_id)

    session_factory = ctx.get("db_session_factory")

    local_engine = None
    if session_factory is None or not isinstance(session_factory, async_sessionmaker):
        local_engine = create_async_engine(settings.DATABASE_URL)
        session_factory = async_sessionmaker(local_engine, class_=AsyncSession, expire_on_commit=False)

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
                    Question.question_type == "subjective",
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
                answer_data.append({
                    "answer_id": a.id,
                    "question_id": q.id,
                    "question_name": q.name,
                    "question_max_score": q.max_score,
                    "image_path": a.image_path,
                })

            # Load rubrics
            rubric_result = await db.execute(
                select(Rubric).where(Rubric.question_id.in_(list(questions.keys())))
            )
            rubrics_by_question = {r.question_id: r.criteria for r in rubric_result.scalars().all()}

            task.total = len(answer_data)
            await db.commit()
            logger.info("grading_task: task=%s, answers=%d, rubrics=%d",
                        task_id, len(answer_data), len(rubrics_by_question))

            errors = []
            for i, ad in enumerate(answer_data):
                answer_id = ad["answer_id"]
                question_id = ad["question_id"]
                question_name = ad["question_name"]
                question_max_score = ad["question_max_score"]
                image_path = ad["image_path"]

                rubric_criteria = rubrics_by_question.get(question_id)
                if rubric_criteria is None:
                    logger.warning("grading_task: no rubric for question=%s", question_id)
                    errors.append({"answer_id": answer_id, "error": f"No rubric for question {question_id}"})
                    task.failed += 1
                    await db.commit()
                    continue

                try:
                    image_b64 = await _read_image_b64(image_path)

                    grade_result = await llm.grade(
                        image_b64=image_b64,
                        rubric={"criteria": rubric_criteria},
                        question={"name": question_name, "max_score": question_max_score},
                    )

                    ai_result = AIGradingResult(
                        task_id=task.id,
                        answer_id=answer_id,
                        question_id=question_id,
                        school_id=task.school_id,
                        score=grade_result.score,
                        max_score=grade_result.max_score,
                        feedback=grade_result.feedback,
                        confidence=grade_result.confidence,
                        raw_response={"raw_content": grade_result.raw_content},
                        review_status="pending",
                    )
                    db.add(ai_result)
                    task.completed += 1
                    await db.commit()
                    logger.info("grading_task: [%d/%d] answer=%s, score=%.1f/%.1f, confidence=%.2f",
                                i + 1, len(answer_data), answer_id,
                                grade_result.score, grade_result.max_score, grade_result.confidence)

                except (ValueError, KeyError, TypeError, RuntimeError) as e:
                    await db.rollback()
                    result = await db.execute(select(GradingTask).where(GradingTask.id == task_id))
                    task = result.scalar_one()
                    errors.append({"answer_id": answer_id, "error": str(e)})
                    task.failed += 1
                    await db.commit()
                    logger.warning("grading_task: [%d/%d] answer=%s FAILED: %s",
                                   i + 1, len(answer_data), answer_id, e)
                except Exception as e:
                    logger.error("grading_task: task=%s UNRECOVERABLE: %s", task_id, e, exc_info=True)
                    await db.rollback()
                    result = await db.execute(select(GradingTask).where(GradingTask.id == task_id))
                    task = result.scalar_one()
                    task.status = "failed"
                    errors.append({"answer_id": answer_id, "error": str(e)})
                    await db.commit()
                    break

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
    """Post-exam pipeline stub — profile snapshots, error book updates, etc."""
    logger.info("post_exam_pipeline START: exam=%s, school=%s", exam_id, school_id)
    # TODO: Implement profile snapshot generation, error book updates
    logger.info("post_exam_pipeline DONE: exam=%s (stub)", exam_id)
