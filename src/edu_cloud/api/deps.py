import logging

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.database import get_db
from edu_cloud.shared.auth import decode_token
from jose import ExpiredSignatureError, JWTError

from edu_cloud.core.permissions import Permission, ROLE_PERMISSIONS
from edu_cloud.services.exceptions import PermissionDeniedError

logger = logging.getLogger(__name__)

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """平台用户认证（JWT）。返回 dict 含 user/roles/current_role/permissions。"""
    try:
        payload = decode_token(credentials.credentials)
    except ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except JWTError:
        raise HTTPException(401, "Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(401, "Invalid token")

    # 优先查新 User 模型
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole

    user = await db.get(User, user_id)
    if user:
        if not user.is_active:
            raise HTTPException(401, "User not found or inactive")

        roles = (
            await db.execute(select(UserRole).where(UserRole.user_id == user.id))
        ).scalars().all()
        if not roles:
            raise HTTPException(403, "No role assigned")

        # 选择活跃角色
        active_role_id = payload.get("active_role_id")
        if active_role_id:
            active = next((r for r in roles if r.id == active_role_id), None)
        else:
            active = next((r for r in roles if r.is_primary), roles[0])

        if active is None:
            active = roles[0]

        return {
            "user": user,
            "roles": roles,
            "current_role": active,
            "permissions": ROLE_PERMISSIONS.get(active.role, set()),
        }

    logger.warning("token user_id=%s not found", user_id)
    raise HTTPException(401, "User not found")


def require_permission(permission: Permission):
    """Factory: returns a FastAPI dependency that checks the user has a permission."""
    async def checker(current: dict = Depends(get_current_user)):
        if permission not in current["permissions"]:
            raise PermissionDeniedError(
                f"Role '{current['current_role'].role}' lacks permission '{permission.value}'"
            )
        return current
    return checker
