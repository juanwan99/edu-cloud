import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.core.auth import require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.database import get_db
from edu_cloud.services.subject_selection_service import (
    list_selections, create_selection, update_selection, delete_selection,
)
from edu_cloud.services.exceptions import ValidationError, NotFoundError, PermissionDeniedError
from edu_cloud.core.tenant import CROSS_SCHOOL_ROLES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/schools/{school_id}", tags=["subject-selections"])


def _check_school_scope(current: dict, school_id: str):
    role = current["current_role"]
    if role.role in CROSS_SCHOOL_ROLES:
        return
    if role.school_id != school_id:
        raise PermissionDeniedError("无权访问其他学校的选考数据")


class CreateSelectionRequest(BaseModel):
    name: str
    subject_codes: list[str]
    mode: str = "custom"


class UpdateSelectionRequest(BaseModel):
    name: str | None = None
    subject_codes: list[str] | None = None
    mode: str | None = None
    is_active: bool | None = None


@router.get("/selections")
async def api_list_selections(
    school_id: str,
    is_active: bool | None = None,
    mode: str | None = None,
    current=Depends(require_permission(Permission.MANAGE_SCHEDULING)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    rows = await list_selections(db, school_id=school_id, is_active=is_active, mode=mode)
    return [
        {"id": s.id, "name": s.name, "subject_codes": s.subject_codes,
         "mode": s.mode, "is_active": s.is_active}
        for s in rows
    ]


@router.post("/selections")
async def api_create_selection(
    school_id: str,
    body: CreateSelectionRequest,
    current=Depends(require_permission(Permission.MANAGE_SCHEDULING)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    sel = await create_selection(
        db, school_id=school_id, name=body.name,
        subject_codes=body.subject_codes, mode=body.mode,
    )
    return {"id": sel.id, "name": sel.name, "subject_codes": sel.subject_codes,
            "mode": sel.mode, "is_active": sel.is_active}


@router.patch("/selections/{selection_id}")
async def api_update_selection(
    school_id: str,
    selection_id: str,
    body: UpdateSelectionRequest,
    current=Depends(require_permission(Permission.MANAGE_SCHEDULING)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    kwargs = {k: v for k, v in body.model_dump().items() if v is not None}
    sel = await update_selection(db, school_id=school_id, selection_id=selection_id, **kwargs)
    return {"id": sel.id, "name": sel.name, "subject_codes": sel.subject_codes,
            "mode": sel.mode, "is_active": sel.is_active}


@router.delete("/selections/{selection_id}")
async def api_delete_selection(
    school_id: str,
    selection_id: str,
    current=Depends(require_permission(Permission.MANAGE_SCHEDULING)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    await delete_selection(db, school_id=school_id, selection_id=selection_id)
    return {"ok": True}
