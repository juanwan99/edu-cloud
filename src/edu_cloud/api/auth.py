import logging

import bcrypt
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from edu_cloud.database import get_db
from edu_cloud.shared.auth import create_access_token, decode_token
from edu_cloud.core.auth import get_current_user
from edu_cloud.logging_config import business_event
from edu_cloud.core.rate_limit import limiter

logger = logging.getLogger(__name__)

_DUMMY_HASH = bcrypt.hashpw(b"timing-defense", bcrypt.gensalt()).decode()

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


async def _build_role_context(role, db):
    """构建角色的上下文对象。"""
    if role.school_id is None:
        if role.role in ("platform_admin", "admin"):
            return {"type": "platform", "id": None, "name": "全平台"}
        elif role.role == "district_admin":
            return {"type": "district", "id": None, "name": "管辖区域"}
        return {"type": "platform", "id": None, "name": "全平台"}

    from edu_cloud.models.school import School
    school = await db.get(School, role.school_id)
    return {
        "type": "school",
        "id": role.school_id,
        "name": school.name if school else "未知学校",
    }


async def _provision_admin_school_roles(user_id: str, existing_roles: list, db):
    """为 platform_admin 自动补全所有活跃学校的角色记录（幂等）。"""
    from edu_cloud.models.school import School
    from edu_cloud.models.user_role import UserRole

    existing_school_ids = {r.school_id for r in existing_roles if r.school_id}
    schools_result = await db.execute(
        select(School).where(School.is_active == True)  # noqa: E712
    )
    schools = schools_result.scalars().all()

    created = []
    for school in schools:
        if school.id in existing_school_ids:
            continue
        role = UserRole(
            user_id=user_id,
            role="platform_admin",
            school_id=school.id,
            is_primary=False,
        )
        db.add(role)
        created.append(role)

    if created:
        await db.commit()
        logger.info("auto-provisioned %d school roles for admin user=%s", len(created), user_id)

    return existing_roles + created


class LoginRequest(BaseModel):
    username: str
    password: str


class SwitchRoleRequest(BaseModel):
    role_id: str


@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, req: LoginRequest, db: AsyncSession = Depends(get_db)):
    # 优先查新 User 模型
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole

    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()

    if not user:
        bcrypt.checkpw(req.password.encode(), _DUMMY_HASH.encode())

    if user and user.verify_password(req.password):
        if not user.is_active:
            raise HTTPException(401, "User is inactive")

        # 查询所有角色
        roles_result = await db.execute(
            select(UserRole).where(UserRole.user_id == user.id)
        )
        roles = list(roles_result.scalars().all())
        if not roles:
            raise HTTPException(403, "No role assigned")

        # platform_admin 自动补全：为所有活跃学校创建学校级角色
        if any(r.role in ("platform_admin", "admin") for r in roles):
            roles = await _provision_admin_school_roles(user.id, roles, db)

        primary = next((r for r in roles if r.is_primary), roles[0])
        token = create_access_token({
            "sub": user.id,
            "role": primary.role,
            "active_role_id": primary.id,
            **({"school_id": primary.school_id} if primary.school_id else {}),
        })
        logger.info("login ok: user=%s, role=%s", req.username, primary.role)
        business_event("login", "user", user.id, role=primary.role)
        roles_data = []
        for r in roles:
            ctx = await _build_role_context(r, db)
            rd = {
                "id": r.id,
                "role": r.role,
                "school_id": r.school_id,
                "is_primary": r.is_primary,
                "context": ctx,
            }
            if r.subject_codes:
                rd["subject_codes"] = r.subject_codes
            if r.class_ids:
                rd["class_ids"] = r.class_ids
            roles_data.append(rd)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "display_name": user.display_name,
                "role": primary.role,
            },
            "roles": roles_data,
        }

    logger.warning("login failed: username=%s", req.username)
    business_event("login_failed", "user", req.username, reason="invalid credentials")
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
        **({"school_id": target_role.school_id} if target_role.school_id else {}),
    })
    ctx = await _build_role_context(target_role, db)
    logger.info("switch-role: user=%s, new_role=%s", user.username, target_role.role)
    return {
        "access_token": token,
        "token_type": "bearer",
        "active_role": {
            "id": target_role.id,
            "role": target_role.role,
            "school_id": target_role.school_id,
            "is_primary": target_role.is_primary,
            "context": ctx,
            **({"subject_codes": target_role.subject_codes} if target_role.subject_codes else {}),
            **({"class_ids": target_role.class_ids} if target_role.class_ids else {}),
        },
    }


@router.post("/logout")
async def logout(request: Request, current: dict = Depends(get_current_user)):
    """Revoke the current token."""
    from edu_cloud.core.token_store import revoke_token
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = decode_token(auth[7:])
            jti = payload.get("jti")
            if jti:
                await revoke_token(jti)
                return {"ok": True}
        except Exception as e:
            logger.warning("logout: token revoke failed: %s", e)
    return {"ok": True}
