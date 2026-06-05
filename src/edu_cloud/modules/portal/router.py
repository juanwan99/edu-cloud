"""Portal aggregation API."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.core.auth import get_current_user
from edu_cloud.database import get_db
from edu_cloud.modules.portal.schemas import (
    CalendarDigestItem,
    MessageItem,
    PortalSummary,
    ServiceEntry,
    TodoItem,
)
from edu_cloud.modules.portal.service import PortalAggregationService

router = APIRouter(prefix="/api/v1/portal", tags=["portal"])


def _service(db: AsyncSession) -> PortalAggregationService:
    return PortalAggregationService(db)


@router.get("/summary", response_model=PortalSummary)
async def get_portal_summary(
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _service(db).summary(current)


@router.get("/todos", response_model=list[TodoItem])
async def get_portal_todos(
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _service(db).list_todos(current)


@router.get("/messages", response_model=list[MessageItem])
async def get_portal_messages(
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _service(db).list_messages(current)


@router.get("/calendar-digest", response_model=list[CalendarDigestItem])
async def get_portal_calendar_digest(
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _service(db).list_calendar_digest(current)


@router.get("/services", response_model=list[ServiceEntry])
async def get_portal_services(
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _service(db).list_services(current)

