import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.notification import Notification

logger = logging.getLogger(__name__)


def _not_sent_summary(channel: str, delivery_state: str) -> dict:
    return {
        "total": 0,
        "success": 0,
        "channel": channel,
        "sent": False,
        "dry_run": channel == "stub",
        "delivery_state": delivery_state,
        "note": "Notification provider is not configured; no message was sent.",
    }


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def dispatch(
        self, document_id: str, target_scope: dict,
        school_id: str, channel: str = "stub",
    ) -> dict:
        """Record a notification dispatch request without faking provider success."""
        existing_result = await self.db.execute(
            select(Notification)
            .where(
                Notification.document_id == document_id,
                Notification.channel != "stub",
                Notification.status.in_(["sent", "partial"]),
            )
            .order_by(Notification.created_at.desc())
            .limit(1)
        )
        existing = existing_result.scalars().first()
        if existing:
            return {
                "status": "already_sent",
                "notification_id": existing.id,
                "channel": existing.channel,
                "sent": True,
                "result": existing.result_summary,
            }

        if channel == "stub":
            legacy_stub_result = await self.db.execute(
                select(Notification)
                .where(
                    Notification.document_id == document_id,
                    Notification.channel == "stub",
                    Notification.status.in_(["sent", "partial"]),
                )
                .order_by(Notification.created_at.desc())
                .limit(1)
            )
            legacy_stub = legacy_stub_result.scalars().first()
            if legacy_stub:
                result_summary = _not_sent_summary("stub", "not_configured")
                result_summary["legacy_status"] = legacy_stub.status
                return {
                    "status": "pending",
                    "notification_id": legacy_stub.id,
                    "channel": legacy_stub.channel,
                    "sent": False,
                    "delivery_state": "not_configured",
                    "result": result_summary,
                }

        pending_result = await self.db.execute(
            select(Notification)
            .where(
                Notification.document_id == document_id,
                Notification.channel == channel,
                Notification.status == "pending",
            )
            .order_by(Notification.created_at.desc())
            .limit(1)
        )
        pending = pending_result.scalars().first()
        if pending:
            result_summary = pending.result_summary or _not_sent_summary(
                channel,
                "not_configured" if channel == "stub" else "pending_provider",
            )
            return {
                "status": pending.status,
                "notification_id": pending.id,
                "channel": pending.channel,
                "sent": False,
                "delivery_state": result_summary.get("delivery_state"),
                "result": result_summary,
            }

        notification = Notification(
            document_id=document_id,
            channel=channel,
            target_scope=target_scope,
            school_id=school_id,
            status="pending",
            sent_at=None,
            result_summary=_not_sent_summary(
                channel,
                "not_configured" if channel == "stub" else "pending_provider",
            ),
        )
        self.db.add(notification)

        if channel == "stub":
            logger.info("Notification recorded only (stub not sent): doc=%s", document_id)

        await self.db.flush()
        return {
            "status": notification.status,
            "notification_id": notification.id,
            "channel": channel,
            "sent": False,
            "delivery_state": notification.result_summary.get("delivery_state"),
            "result": notification.result_summary,
        }
