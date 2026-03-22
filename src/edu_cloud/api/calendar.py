from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.api.deps import get_current_user, require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.database import get_db
from edu_cloud.services.calendar_service import CalendarService

router = APIRouter(prefix="/api/v1/calendar", tags=["calendar"])


@router.post("/events", status_code=201)
async def create_event(
    body: dict,
    current=Depends(require_permission(Permission.GENERATE_NOTIFICATION)),
    db: AsyncSession = Depends(get_db),
):
    for field in ("type", "title", "event_date"):
        if field not in body:
            raise HTTPException(422, f"缺少必填字段: {field}")
    try:
        event_date = date.fromisoformat(body["event_date"])
    except (ValueError, TypeError):
        raise HTTPException(422, f"日期格式无效: {body['event_date']}")
    user = current["user"]
    role = current["current_role"]
    svc = CalendarService(db)
    event = await svc.create_event(
        type=body["type"], title=body["title"],
        event_date=event_date,
        school_id=getattr(role, "school_id", ""),
        created_by=user.id,
        semester=body.get("semester"),
        description=body.get("description"),
        notification_rules=body.get("notification_rules", []),
    )
    return _event_to_dict(event)


@router.get("/events")
async def list_events(
    start: str | None = None, end: str | None = None,
    current=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    role = current["current_role"]
    svc = CalendarService(db)
    events = await svc.list_events(
        school_id=getattr(role, "school_id", ""),
        start_date=date.fromisoformat(start) if start else None,
        end_date=date.fromisoformat(end) if end else None,
    )
    return [_event_to_dict(e) for e in events]


@router.delete("/events/{event_id}")
async def delete_event(
    event_id: str,
    current=Depends(require_permission(Permission.GENERATE_NOTIFICATION)),
    db: AsyncSession = Depends(get_db),
):
    role = current["current_role"]
    svc = CalendarService(db)
    await svc.delete_event(event_id, school_id=getattr(role, "school_id", ""))
    return {"status": "deleted"}


def _event_to_dict(event) -> dict:
    return {
        "id": event.id,
        "type": event.type,
        "title": event.title,
        "event_date": str(event.event_date),
        "semester": event.semester,
        "is_active": event.is_active,
    }
