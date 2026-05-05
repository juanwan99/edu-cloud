"""
arq worker 入口。
启动方式: arq edu_cloud.worker.WorkerSettings
PM2: pm2 start arq -- edu_cloud.worker.WorkerSettings
"""
import logging
from datetime import datetime
from arq import cron
from arq.connections import RedisSettings
from edu_cloud.config import settings
from edu_cloud.database import async_session
from edu_cloud.tasks import auto_draft_notifications
from edu_cloud.workers.grading import process_grading_task, run_post_exam_pipeline
from edu_cloud.ai.runtime import SCHEDULED_PROMPTS

logger = logging.getLogger(__name__)


async def run_auto_draft(ctx):
    """arq cron job: 每天 6:00 (UTC+8 = 22:00 UTC) 扫描日历"""
    async with async_session() as db:
        count = await auto_draft_notifications(db)
        logger.info(f"Auto-draft job completed: {count} notifications created")


async def run_w3_daily(ctx):
    """arq cron: W3 学情画像 — 每天 04:00 UTC+8 = 20:00 UTC

    W3 steps use trigger_ref as exam_id, so we iterate recent published
    exams (last 24h) and run W3 once per exam per school.
    """
    from edu_cloud.ai.workflow.engine import WorkflowExecutor
    from edu_cloud.ai.workflow.w3_student_profile import W3_STUDENT_PROFILE
    from sqlalchemy import select
    from edu_cloud.models.school import School
    from edu_cloud.modules.exam.models import Exam
    from datetime import timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    async with async_session() as db:
        schools = (await db.execute(
            select(School).where(School.is_active == True)  # noqa: E712
        )).scalars().all()
        for school in schools:
            # Find exams published in the last 24h for this school
            exams = (await db.execute(
                select(Exam).where(
                    Exam.school_id == school.id,
                    Exam.status == "published",
                    Exam.updated_at >= cutoff,
                )
            )).scalars().all()
            if not exams:
                continue
            for exam in exams:
                try:
                    executor = WorkflowExecutor(db)
                    await executor.execute(
                        workflow=W3_STUDENT_PROFILE, school_id=school.id,
                        trigger_type="schedule", trigger_ref=exam.id,
                    )
                except Exception as e:
                    logger.error("W3 failed for school %s exam %s: %s", school.id, exam.id, e)


async def run_w6_hourly(ctx):
    """arq cron: W6 异常巡检 — 每小时"""
    from edu_cloud.ai.workflow.engine import WorkflowExecutor
    from edu_cloud.ai.workflow.w6_patrol import W6_PATROL
    from sqlalchemy import select
    from edu_cloud.models.school import School

    async with async_session() as db:
        schools = (await db.execute(
            select(School).where(School.is_active == True)  # noqa: E712
        )).scalars().all()
        for school in schools:
            try:
                executor = WorkflowExecutor(db)
                await executor.execute(
                    workflow=W6_PATROL, school_id=school.id,
                    trigger_type="schedule", trigger_ref=f"hourly:{datetime.now().hour:02d}",
                )
            except Exception as e:
                logger.error("W6 failed for school %s: %s", school.id, e)


async def run_agent_scheduled(ctx, school_id: str, task_type: str, params: dict = None):
    """Scheduled Agent task — uses school's own model slots."""
    prompt = SCHEDULED_PROMPTS.get(task_type)
    if not prompt:
        logger.warning("Unknown agent task_type: %s", task_type)
        return
    # Full implementation deferred to Phase C — this is the interface hook
    logger.info("Agent scheduled task: school=%s type=%s", school_id, task_type)


async def on_worker_startup(ctx):
    """Worker startup hook: initialize logging for worker process."""
    from edu_cloud.logging_config import setup_logging
    setup_logging(process="worker")
    logger.info("arq worker started, logging initialized (process=worker)")


class WorkerSettings:
    """arq WorkerSettings — 通过 `arq edu_cloud.worker.WorkerSettings` 启动"""
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    job_timeout = 1800
    on_startup = on_worker_startup
    cron_jobs = [
        cron(run_auto_draft, hour=22, minute=0),  # 22:00 UTC = 06:00 UTC+8
        cron(run_w3_daily, hour=20, minute=0),     # 20:00 UTC = 04:00 UTC+8
        cron(run_w6_hourly, minute=0),             # every hour at :00
    ]
    functions = [
        run_auto_draft,
        process_grading_task,
        run_post_exam_pipeline,
        run_w3_daily,
        run_w6_hourly,
        run_agent_scheduled,
    ]
