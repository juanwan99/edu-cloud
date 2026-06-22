"""
arq worker 入口。
启动方式: arq edu_cloud.worker.WorkerSettings
PM2: pm2 start arq -- edu_cloud.worker.WorkerSettings
"""
import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from arq import cron
from arq.connections import RedisSettings
from edu_cloud.config import settings
from edu_cloud.database import async_session
from edu_cloud.tasks import auto_draft_notifications
from edu_cloud.workers.grading import process_grading_task, run_post_exam_pipeline
from edu_cloud.ai.prompts import SCHEDULED_PROMPTS

logger = logging.getLogger(__name__)

_WORKER_BOOT_TIME = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
_WORKER_RUNTIME_STATE_ENV = "EDU_CLOUD_WORKER_RUNTIME_STATE"
_WORKER_SOURCE_PATHS = ("src/", "scripts/run-arq-worker", "pyproject.toml", "uv.lock")


def _repo_root() -> Path:
    try:
        return Path(
            subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        )
    except Exception:
        return Path(__file__).resolve().parents[2]


def _git_text(repo: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=repo,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def _is_worker_source_dirty(repo: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", *_WORKER_SOURCE_PATHS],
            cwd=repo,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
        return result.returncode != 0
    except Exception:
        return True


def worker_runtime_fingerprint() -> dict[str, object]:
    repo = _repo_root()
    return {
        "schema": "edu-cloud.worker-runtime.v1",
        "service": "edu-cloud-worker",
        "process": "worker",
        "pid": os.getpid(),
        "boot_time": _WORKER_BOOT_TIME,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "git_hash": _git_text(repo, "rev-parse", "--short", "HEAD"),
        "source_dirty": _is_worker_source_dirty(repo),
        "source_paths": list(_WORKER_SOURCE_PATHS),
    }


def record_worker_runtime_state(path: str | Path | None = None) -> dict[str, object]:
    repo = _repo_root()
    state_path = Path(path or os.environ.get(_WORKER_RUNTIME_STATE_ENV, repo / "logs" / "worker-runtime.json"))
    payload = worker_runtime_fingerprint()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = state_path.with_name(f".{state_path.name}.{os.getpid()}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(state_path)
    return {**payload, "state_path": str(state_path)}


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
    """Worker startup hook: initialize logging and run health checks."""
    from edu_cloud.logging_config import setup_logging
    from edu_cloud.startup_checks import run_startup_checks
    from edu_cloud.config import settings
    setup_logging(process="worker")
    await run_startup_checks(settings)
    try:
        runtime = record_worker_runtime_state()
        logger.info(
            "arq worker runtime state recorded: git=%s pid=%s path=%s",
            runtime.get("git_hash"),
            runtime.get("pid"),
            runtime.get("state_path"),
        )
    except Exception as exc:
        logger.warning("failed to record arq worker runtime state: %s", exc)
    logger.info("arq worker started, all checks passed (process=worker)")


class WorkerSettings:
    """arq WorkerSettings — 通过 `arq edu_cloud.worker.WorkerSettings` 启动"""
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 8
    job_timeout = 7200
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
