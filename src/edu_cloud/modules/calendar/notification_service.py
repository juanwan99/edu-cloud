import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.models.notification import Notification

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def dispatch(
        self, document_id: str, target_scope: dict,
        school_id: str, channel: str = "stub",
    ) -> dict:
        """分发通知。首期 stub 模式直接标记 sent。"""
        # 幂等检查
        existing = (await self.db.execute(
            select(Notification).where(
                Notification.document_id == document_id,
                Notification.status.in_(["sent", "partial"]),
            )
        )).scalar_one_or_none()
        if existing:
            return {"status": "already_sent", "notification_id": existing.id, "channel": channel}

        # 创建通知记录
        notification = Notification(
            document_id=document_id,
            channel=channel,
            target_scope=target_scope,
            school_id=school_id,
        )
        self.db.add(notification)

        if channel == "stub":
            notification.status = "sent"
            notification.sent_at = datetime.now(timezone.utc)
            notification.result_summary = {"total": 0, "success": 0, "channel": "stub", "note": "企业微信未接入，仅标记状态"}
            logger.info(f"Notification dispatched (stub): doc={document_id}")
        else:
            notification.status = "pending"

        await self.db.flush()
        return {
            "status": notification.status,
            "notification_id": notification.id,
            "channel": channel,
            "result": notification.result_summary,
        }
