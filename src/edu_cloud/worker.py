"""
arq worker 入口。
启动方式: arq edu_cloud.worker.WorkerSettings
PM2: pm2 start arq -- edu_cloud.worker.WorkerSettings
"""
import logging
from arq import cron
from arq.connections import RedisSettings
from edu_cloud.config import settings
from edu_cloud.database import async_session
from edu_cloud.tasks import auto_draft_notifications

logger = logging.getLogger(__name__)


async def run_auto_draft(ctx):
    """arq cron job: 每天 6:00 (UTC+8 = 22:00 UTC) 扫描日历"""
    async with async_session() as db:
        count = await auto_draft_notifications(db)
        logger.info(f"Auto-draft job completed: {count} notifications created")


class WorkerSettings:
    """arq WorkerSettings — 通过 `arq edu_cloud.worker.WorkerSettings` 启动"""
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    cron_jobs = [
        cron(run_auto_draft, hour=22, minute=0),  # 22:00 UTC = 06:00 UTC+8
    ]
    functions = [run_auto_draft]
