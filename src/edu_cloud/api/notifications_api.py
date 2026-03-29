"""Notifications List API — 按角色 scope 过滤通知。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta, timezone

from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user
from edu_cloud.models.notification import Notification
from edu_cloud.models.document import Document

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

# Document.type → 前端 kind 映射
_KIND_MAP = {"notification": "message", "approval": "approval"}


@router.get("")
async def list_notifications(
    status: str | None = Query(None),
    since: str | None = Query(None),
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    role = current["current_role"]
    school_id = role.school_id

    q = (select(Notification, Document.title, Document.type)
         .join(Document, Notification.document_id == Document.id)
         .order_by(Notification.created_at.desc()))
    if school_id:
        q = q.where(Notification.school_id == school_id)
    if status:
        q = q.where(Notification.status == status)
    if since == "week":
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        q = q.where(Notification.created_at >= cutoff)

    result = await db.execute(q.limit(50))
    rows = result.all()
    return [
        {
            "id": n.id,
            "status": n.status,
            "channel": n.channel,
            "created_at": str(n.created_at),
            "title": doc_title or f"通知 {n.id[:8]}",
            "summary": None,
            "kind": _KIND_MAP.get(doc_type, "system"),
            "unread": n.status == "pending",
        }
        for n, doc_title, doc_type in rows
    ]
