import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.api.deps import get_current_user, require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.database import get_db
from edu_cloud.services.school_settings_service import (
    get_settings, upsert_setting, get_all_modules,
    set_module_enabled, get_enabled_modules, init_school_modules,
)
from edu_cloud.services.exceptions import ValidationError, PermissionDeniedError
from edu_cloud.logging_config import business_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/schools/{school_id}", tags=["school-settings"])

# Roles that are not bound to a single school (can manage any school)
_CROSS_SCHOOL_ROLES = {"platform_admin", "district_admin"}


def _check_school_scope(current: dict, school_id: str):
    """Ensure school-scoped roles only access their own school."""
    role = current["current_role"]
    if role.role in _CROSS_SCHOOL_ROLES:
        return
    if role.school_id != school_id:
        raise PermissionDeniedError("无权访问其他学校的配置")


class UpsertSettingRequest(BaseModel):
    category: str = "general"
    key: str
    value: str | None = None


class ToggleModuleRequest(BaseModel):
    enabled: bool


@router.get("/settings")
async def list_settings(
    school_id: str,
    category: str | None = None,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL_CONFIG)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    settings = await get_settings(db, school_id=school_id, category=category)
    return [
        {"id": s.id, "category": s.category, "key": s.key, "value": s.value}
        for s in settings
    ]


@router.patch("/settings")
async def update_setting(
    school_id: str,
    body: UpsertSettingRequest,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL_CONFIG)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    result = await upsert_setting(
        db, school_id=school_id,
        category=body.category,
        key=body.key,
        value=body.value,
    )
    return {"id": result.id, "category": result.category, "key": result.key, "value": result.value}


@router.get("/modules")
async def list_modules(
    school_id: str,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL_CONFIG)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    await init_school_modules(db, school_id=school_id)
    return await get_all_modules(db, school_id=school_id)


@router.get("/modules/enabled")
async def list_enabled_modules(
    school_id: str,
    current=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    await init_school_modules(db, school_id=school_id)
    return list(await get_enabled_modules(db, school_id=school_id))


@router.patch("/modules/{module_code}")
async def toggle_module(
    school_id: str,
    module_code: str,
    body: ToggleModuleRequest,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL_CONFIG)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    try:
        module = await set_module_enabled(
            db, school_id=school_id, module_code=module_code, enabled=body.enabled,
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    old_state = "disabled" if body.enabled else "enabled"
    new_state = "enabled" if body.enabled else "disabled"
    business_event(
        "module_toggle", "school_module", f"{school_id}:{module_code}",
        old_state=old_state, new_state=new_state,
    )
    return {"code": module.module_code, "enabled": module.enabled}
