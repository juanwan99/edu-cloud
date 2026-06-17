"""成绩发布 Service — publish/archive 专��入口。"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.exam.models import Exam
from edu_cloud.modules.grading.models import GradingAssignment, GradingQualityCheck
from edu_cloud.core.state_machine import validate_transition
from edu_cloud.services.exceptions import StateError
from edu_cloud.logging_config import business_event

logger = logging.getLogger(__name__)


class ExamPublishService:
    @staticmethod
    async def publish(db: AsyncSession, *, exam_id: str, school_id: str) -> dict:
        from edu_cloud.modules.exam.service import get_exam
        exam = await get_exam(db, exam_id=exam_id, school_id=school_id)
        if exam.status != "completed":
            raise StateError(
                f"Cannot publish exam in status '{exam.status}'"
            )

        # 前置条件: 所有阅卷任务已完成
        stmt = select(GradingAssignment).where(GradingAssignment.exam_id == exam_id)
        result = await db.execute(stmt)
        assignments = list(result.scalars().all())
        incomplete = [a for a in assignments if a.status != "completed"]
        if incomplete:
            raise StateError(f"{len(incomplete)} grading assignments not completed")

        # 前置条���: 无 HIGH severity 质量问题
        stmt = select(GradingQualityCheck).where(
            GradingQualityCheck.exam_id == exam_id,
            GradingQualityCheck.severity == "high",
        )
        result = await db.execute(stmt)
        high_issues = list(result.scalars().all())
        if high_issues:
            raise StateError(f"{len(high_issues)} high-severity quality issues unresolved")

        old_status = exam.status
        validate_transition("exam", old_status, "published")
        exam.status = "published"
        await db.flush()
        logger.info("exam_published: exam_id=%s, school_id=%s", exam_id, school_id)
        business_event("state_change", "exam", exam_id, old_state=old_status, new_state="published")

        # 触发发布后流程（stub）
        await ExamPublishService._calculate_rankings(db, exam_id, school_id)
        await ExamPublishService._update_error_books(db, exam_id, school_id)

        # EventBus 通知（失败不阻塞发布）
        try:
            from edu_cloud.core.events import event_bus
            await event_bus.emit("exam.published", {
                "exam_id": exam_id, "school_id": school_id,
            })
        except Exception:
            logger.warning("event_bus.emit failed for exam.published", exc_info=True)

        return {"exam_id": exam_id, "status": "published"}

    @staticmethod
    async def _calculate_rankings(db, exam_id, school_id):
        """排名计算 — 委托模块外编排服务 exam_publish_pipeline.publish_rankings。

        exam 不再直接 import pipeline（D-03C）；跨模块调用集中在 services 层。
        """
        from edu_cloud.services.exam_publish_pipeline import publish_rankings
        await publish_rankings(db, exam_id=exam_id, school_id=school_id)

    @staticmethod
    async def _update_error_books(db, exam_id, school_id):
        """错题更新 — 委托模块外编排服务 exam_publish_pipeline.publish_error_books。"""
        from edu_cloud.services.exam_publish_pipeline import publish_error_books
        await publish_error_books(db, exam_id=exam_id, school_id=school_id)

    @staticmethod
    async def archive(db: AsyncSession, *, exam_id: str, school_id: str) -> None:
        from edu_cloud.modules.exam.service import get_exam
        exam = await get_exam(db, exam_id=exam_id, school_id=school_id)
        if exam.status != "published":
            raise StateError(
                f"Cannot archive exam in status '{exam.status}'"
            )
        old_status = exam.status
        validate_transition("exam", old_status, "archived")
        exam.status = "archived"
        await db.flush()
        logger.info("exam_archived: exam_id=%s, school_id=%s", exam_id, school_id)
        business_event("state_change", "exam", exam_id, old_state=old_status, new_state="archived")
