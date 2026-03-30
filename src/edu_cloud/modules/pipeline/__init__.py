"""Pipeline 模块 — 考后数据流水线。

EventBus handler 在此注册，确保 import 时自动激活。
"""
import logging
from edu_cloud.core.events import event_bus

logger = logging.getLogger(__name__)


@event_bus.on("exam.published")
async def on_exam_published(payload: dict) -> None:
    """成绩发布后触发完整流水线（知识点掌握度 + 错误模式）。

    注意：排名和错题已在 publish_service 同步处理，
    此 handler 补充异步处理的部分（掌握度更新 + 错误模式聚合）。
    """
    exam_id = payload.get("exam_id")
    school_id = payload.get("school_id")
    if not exam_id or not school_id:
        logger.warning("on_exam_published: missing exam_id or school_id")
        return

    from edu_cloud.database import async_session
    from edu_cloud.modules.pipeline.service import update_knowledge_mastery, update_error_patterns

    async with async_session() as db:
        mastery = await update_knowledge_mastery(db, exam_id=exam_id, school_id=school_id)
        patterns = await update_error_patterns(db, exam_id=exam_id, school_id=school_id)
        await db.commit()
    logger.info(
        "on_exam_published: exam=%s, mastery=%d, patterns=%d",
        exam_id, mastery, patterns,
    )