"""Conduct notification API routes — parent pulls notifications."""
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.core.auth import get_current_user
from edu_cloud.modules.conduct.models import ConductNotification

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/conduct", tags=["conduct-notifications"])


@router.get("/parent/notifications")
async def get_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pull notification list for the current parent user."""
    user = current_user["user"]
    stmt = (
        select(ConductNotification)
        .where(ConductNotification.parent_user_id == user.id)
    )
    if unread_only:
        stmt = stmt.where(ConductNotification.is_read == False)  # noqa: E712
    stmt = stmt.order_by(ConductNotification.created_at.desc()).limit(limit)

    notifications = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": n.id,
            "title": n.title,
            "body": n.body,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
            "student_id": n.student_id,
        }
        for n in notifications
    ]


@router.post("/parent/notifications/read-all")
async def mark_all_read(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all unread notifications as read for the current parent."""
    user = current_user["user"]
    await db.execute(
        update(ConductNotification)
        .where(
            ConductNotification.parent_user_id == user.id,
            ConductNotification.is_read == False,  # noqa: E712
        )
        .values(is_read=True)
    )
    await db.commit()
    return {"ok": True}
