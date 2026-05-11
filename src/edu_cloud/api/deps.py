import logging
from dataclasses import dataclass

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.database import get_db
from edu_cloud.shared.auth import decode_token
from jwt import ExpiredSignatureError, InvalidTokenError as JWTError

from edu_cloud.core.permissions import Permission, ROLE_PERMISSIONS
from edu_cloud.services.exceptions import PermissionDeniedError

# Allowlist: only these permissions survive during impersonation.
# H-1: USE_AI_CHAT and GENERATE_REPORT removed — AI chat grants access to
# the full data domain, and report generation is a write-equivalent operation.
_IMPERSONATION_ALLOWED_PERMISSIONS = {
    Permission.VIEW_SCHOOLS,
    Permission.VIEW_JOINT_EXAM,
    Permission.VIEW_CROSS_SCHOOL_ANALYTICS,
    Permission.VIEW_QUESTION_BANK,
    Permission.VIEW_STUDENTS,
    Permission.VIEW_EXAMS,
    Permission.VIEW_SCORES,
    Permission.VIEW_GRADING,
    Permission.VIEW_HOMEWORK,
    Permission.VIEW_KNOWLEDGE_TREE,
    Permission.VIEW_CONDUCT,
}
from edu_cloud.logging_config import business_event

logger = logging.getLogger(__name__)


@dataclass
class ImpersonatedRole:
    """Virtual role object for impersonation, duck-type compatible with UserRole."""

    id: str
    user_id: str
    role: str
    school_id: str | None
    class_ids: list[str] | None = None
    subject_codes: list[str] | None = None
    grade_ids: list[str] | None = None
    is_primary: bool = False
    is_impersonation: bool = True


security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """平台用户认证（JWT）。返回 dict 含 user/roles/current_role/permissions。"""
    try:
        payload = decode_token(credentials.credentials)
    except ExpiredSignatureError:
        # C-1 fix: expired tokens are always rejected, including impersonation.
        # Impersonation tokens have a 30-min hard expiry; there is no grace period.
        logger.info("token_expired: impersonation or normal token rejected")
        raise HTTPException(401, "Token expired")
    except JWTError:
        raise HTTPException(401, "Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(401, "Invalid token")

    # ── Impersonation 分支 ──
    if payload.get("is_impersonation"):
        # Fail-closed: 必须包含完整 claims
        effective_role = payload.get("effective_role")
        effective_school_id = payload.get("effective_school_id")
        scope_override = payload.get("scope_override")
        if not effective_role or not effective_school_id or scope_override is None:
            raise HTTPException(401, "Malformed impersonation token")

        from edu_cloud.logging_config import impersonator_var
        impersonator_id = payload.get("impersonator_id", user_id)
        impersonator_var.set(impersonator_id)

        from edu_cloud.models.user import User
        from edu_cloud.models.user_role import UserRole

        user = await db.get(User, impersonator_id)
        if not user or not user.is_active:
            raise HTTPException(401, "Impersonator user not found or inactive")

        # 验证 impersonator 是 platform_admin
        admin_roles = (
            await db.execute(
                select(UserRole).where(
                    UserRole.user_id == impersonator_id,
                    UserRole.role.in_(["platform_admin", "admin"]),
                )
            )
        ).scalars().all()
        if not admin_roles:
            raise HTTPException(403, "Only platform_admin can impersonate")

        virtual_role = ImpersonatedRole(
            id=f"imp-{impersonator_id[:8]}",
            user_id=impersonator_id,
            role=effective_role,
            school_id=effective_school_id,
            class_ids=scope_override.get("class_ids"),
            subject_codes=scope_override.get("subject_codes"),
            grade_ids=scope_override.get("grade_ids"),
        )

        full_perms = ROLE_PERMISSIONS.get(effective_role, set())
        read_only_perms = full_perms & _IMPERSONATION_ALLOWED_PERMISSIONS
        return {
            "user": user,
            "roles": [],
            "current_role": virtual_role,
            "permissions": read_only_perms,
            "is_impersonation": True,
            "impersonator_id": impersonator_id,
        }

    # ── 正常认证分支 ──
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
            business_event(
                "permission_denied", "user", current["user"].id,
                reason=f"missing {permission.value}",
            )
            raise PermissionDeniedError(
                f"Role '{current['current_role'].role}' lacks permission '{permission.value}'"
            )
        return current
    return checker


from edu_cloud.core.tenant import TenantContext, get_school_id
from edu_cloud.api.permissions import get_visible_class_ids, get_visible_subject_codes


def _to_tuple(lst: list | None) -> tuple | None:
    return None if lst is None else tuple(lst)


async def get_tenant_context(
    current: dict = Depends(get_current_user),
) -> TenantContext:
    role = current["current_role"]
    return TenantContext(
        user_id=str(current["user"].id),
        role_id=str(role.id),
        role_name=role.role,
        school_id=get_school_id(current),
        visible_class_ids=_to_tuple(get_visible_class_ids(role)),
        visible_subject_codes=_to_tuple(get_visible_subject_codes(role)),
    )
