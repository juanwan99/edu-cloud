import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.api.deps import require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.database import get_db
from edu_cloud.services.capability_service import (
    init_school_capabilities, get_capabilities, set_capability,
)
from edu_cloud.services.exceptions import PermissionDeniedError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/schools/{school_id}", tags=["capabilities"])

_CROSS_SCHOOL_ROLES = {"platform_admin", "district_admin"}


def _check_school_scope(current: dict, school_id: str):
    role = current["current_role"]
    if role.role in _CROSS_SCHOOL_ROLES:
        return
    if role.school_id != school_id:
        raise PermissionDeniedError("无权访问其他学校的能力配置")


class PatchCapabilityRequest(BaseModel):
    role: str
    domain: str
    action: str
    enabled: bool


@router.get("/capabilities")
async def api_get_capabilities(
    school_id: str,
    role: str | None = None,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    caps = await get_capabilities(db, school_id=school_id, role=role)
    return [
        {
            "id": c.id, "role": c.role, "domain": c.domain,
            "action": c.action, "enabled": c.enabled,
        }
        for c in caps
    ]


@router.patch("/capabilities")
async def api_patch_capability(
    school_id: str,
    body: PatchCapabilityRequest,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    cap = await set_capability(
        db, school_id=school_id, role=body.role,
        domain=body.domain, action=body.action, enabled=body.enabled,
    )
    return {
        "id": cap.id, "role": cap.role, "domain": cap.domain,
        "action": cap.action, "enabled": cap.enabled,
    }


@router.post("/capabilities/init")
async def api_init_capabilities(
    school_id: str,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    await init_school_capabilities(db, school_id=school_id)
    return {"ok": True}
