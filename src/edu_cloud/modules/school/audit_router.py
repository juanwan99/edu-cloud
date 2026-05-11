import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.core.auth import require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.database import get_db
from edu_cloud.services.audit_service import list_audit_logs
from edu_cloud.services.exceptions import PermissionDeniedError
from edu_cloud.core.tenant import CROSS_SCHOOL_ROLES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/schools/{school_id}", tags=["audit-logs"])


def _check_school_scope(current: dict, school_id: str):
    role = current["current_role"]
    if role.role in CROSS_SCHOOL_ROLES:
        return
    if role.school_id != school_id:
        raise PermissionDeniedError("无权访问其他学校的审计日志")


@router.get("/audit-logs")
async def api_list_audit_logs(
    school_id: str,
    entity_type: str | None = None,
    user_id: str | None = None,
    action: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current=Depends(require_permission(Permission.MANAGE_SCHOOL_CONFIG)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    logs, total = await list_audit_logs(
        db, school_id=school_id,
        entity_type=entity_type, user_id=user_id, action=action,
        start_date=start_date, end_date=end_date,
        limit=limit, offset=offset,
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": log.id,
                "school_id": log.school_id,
                "user_id": log.user_id,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "action": log.action,
                "before_data": log.before_data,
                "after_data": log.after_data,
                "request_id": log.request_id,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
    }
