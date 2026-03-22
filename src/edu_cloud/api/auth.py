import logging

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.database import get_db
from edu_cloud.shared.auth import create_access_token
from edu_cloud.api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class SwitchRoleRequest(BaseModel):
    role_id: str


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    # 优先查新 User 模型
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole

    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()

    if user and user.verify_password(req.password):
        if not user.is_active:
            raise HTTPException(401, "User is inactive")

        # 查询所有角色
        roles_result = await db.execute(
            select(UserRole).where(UserRole.user_id == user.id)
        )
        roles = roles_result.scalars().all()
        if not roles:
            raise HTTPException(403, "No role assigned")

        primary = next((r for r in roles if r.is_primary), roles[0])
        token = create_access_token({
            "sub": user.id,
            "role": primary.role,
            "active_role_id": primary.id,
        })
        logger.info("login ok: user=%s, role=%s", req.username, primary.role)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "display_name": user.display_name,
                "role": primary.role,
            },
            "roles": [
                {
                    "id": r.id,
                    "role": r.role,
                    "school_id": r.school_id,
                    "is_primary": r.is_primary,
                }
                for r in roles
            ],
        }

    logger.warning("login failed: username=%s", req.username)
    raise HTTPException(401, "Invalid credentials")


@router.post("/switch-role")
async def switch_role(
    req: SwitchRoleRequest,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """切换当前活跃角色，返回新 token。"""
    from edu_cloud.models.user_role import UserRole

    user = current["user"]

    # 验证目标角色存在且属于当前用户
    result = await db.execute(
        select(UserRole).where(
            UserRole.id == req.role_id,
            UserRole.user_id == user.id,
        )
    )
    target_role = result.scalar_one_or_none()
    if not target_role:
        raise HTTPException(404, "Role not found")

    token = create_access_token({
        "sub": user.id,
        "role": target_role.role,
        "active_role_id": target_role.id,
    })
    logger.info("switch-role: user=%s, new_role=%s", user.username, target_role.role)
    return {
        "access_token": token,
        "token_type": "bearer",
        "active_role": {
            "id": target_role.id,
            "role": target_role.role,
            "school_id": target_role.school_id,
            "is_primary": target_role.is_primary,
        },
    }
