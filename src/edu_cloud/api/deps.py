import logging

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.database import get_db
from edu_cloud.models.platform_user import PlatformUser
from edu_cloud.shared.auth import decode_token
from jose import ExpiredSignatureError, JWTError

from edu_cloud.core.permissions import Permission, has_permission
from edu_cloud.services.exceptions import PermissionDeniedError

logger = logging.getLogger(__name__)

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> PlatformUser:
    """平台用户认证（JWT）。用于管理端。"""
    try:
        payload = decode_token(credentials.credentials)
    except ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except JWTError:
        raise HTTPException(401, "Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(401, "Invalid token")

    result = await db.execute(select(PlatformUser).where(PlatformUser.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        logger.warning("token user_id=%s not found", user_id)
        raise HTTPException(401, "User not found")
    return user


def require_permission(permission: Permission):
    """Factory: returns a FastAPI dependency that checks the user has a permission."""
    async def checker(user: PlatformUser = Depends(get_current_user)):
        if not has_permission(user.role, permission):
            raise PermissionDeniedError(
                f"Role '{user.role}' lacks permission '{permission.value}'"
            )
        return user
    return checker
