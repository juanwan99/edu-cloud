"""角色模拟 API — 仅 platform_admin 可用。

NOTE: 当前实现授予模拟角色的完整权限（含写操作）。
后续版本可能收回为只读模式。
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.core.auth import get_current_user
from edu_cloud.core.permissions import ROLE_PERMISSIONS
from edu_cloud.database import get_db
from edu_cloud.logging_config import business_event
from edu_cloud.shared.auth import create_access_token, create_impersonation_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

IMPERSONATABLE_ROLES = [
    "school_admin",
    "principal",
    "academic_director",
    "teaching_research_leader",
    "grade_leader",
    "lesson_prep_leader",
    "homeroom_teacher",
    "subject_teacher",
]

# Roles that require specific scope fields
SCOPE_REQUIRED = {
    "subject_teacher": ["class_ids", "subject_codes"],
    "homeroom_teacher": ["class_ids"],
    "grade_leader": ["grade_ids"],
    "lesson_prep_leader": ["grade_ids", "subject_codes"],
    "teaching_research_leader": ["subject_codes"],
}


class ImpersonateRequest(BaseModel):
    school_id: str
    role: str
    scope: dict = {}

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        if v not in IMPERSONATABLE_ROLES:
            raise ValueError(
                f"Invalid role '{v}'. Must be one of: {IMPERSONATABLE_ROLES}"
            )
        return v


@router.post("/impersonate")
async def impersonate(
    req: ImpersonateRequest,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """进入角色模拟。仅 platform_admin 可调用。"""
    user = current["user"]

    # 权限校验：必须是 platform_admin
    role_name = current["current_role"].role
    if role_name not in ("platform_admin", "admin"):
        raise HTTPException(403, "Only platform_admin can impersonate")

    # 验证目标学校存在且活跃
    from edu_cloud.models.school import School
    school = await db.get(School, req.school_id)
    if not school or not school.is_active:
        raise HTTPException(404, "School not found or inactive")

    # 按角色校验必填 scope（含类型检查）
    required_fields = SCOPE_REQUIRED.get(req.role, [])
    for field_name in required_fields:
        value = req.scope.get(field_name)
        if not value:
            raise HTTPException(
                422,
                f"Role '{req.role}' requires non-empty scope field: {field_name}",
            )
        if not isinstance(value, list):
            raise HTTPException(
                422,
                f"Scope field '{field_name}' must be a list",
            )

    def _validate_str_list(field_name: str, val: list) -> list[str]:
        if not all(isinstance(v, str) for v in val):
            raise HTTPException(422, f"{field_name} elements must be strings")
        return val

    # 校验 scope 中的 class_ids 属于目标学校
    if req.scope.get("class_ids"):
        from edu_cloud.modules.student.models import Class
        class_ids = req.scope["class_ids"]
        if not isinstance(class_ids, list):
            raise HTTPException(422, "class_ids must be a list")
        class_ids = _validate_str_list("class_ids", class_ids)
        result = await db.execute(
            select(Class.id).where(
                Class.id.in_(class_ids),
                Class.school_id == req.school_id,
            )
        )
        valid_ids = set(result.scalars().all())
        invalid = set(class_ids) - valid_ids
        if invalid:
            raise HTTPException(422, f"Classes not in target school: {list(invalid)}")

    if req.scope.get("grade_ids"):
        from edu_cloud.models.grade import Grade
        grade_ids = req.scope["grade_ids"]
        if not isinstance(grade_ids, list):
            raise HTTPException(422, "grade_ids must be a list")
        grade_ids = _validate_str_list("grade_ids", grade_ids)
        result = await db.execute(
            select(Grade.id).where(
                Grade.id.in_(grade_ids),
                Grade.school_id == req.school_id,
            )
        )
        valid_ids = set(result.scalars().all())
        invalid = set(grade_ids) - valid_ids
        if invalid:
            raise HTTPException(422, f"Grades not in target school: {list(invalid)}")

    if req.scope.get("subject_codes"):
        from edu_cloud.modules.exam.models import Subject
        subject_codes = req.scope["subject_codes"]
        if not isinstance(subject_codes, list):
            raise HTTPException(422, "subject_codes must be a list")
        subject_codes = _validate_str_list("subject_codes", subject_codes)
        result = await db.execute(
            select(Subject.code).where(
                Subject.code.in_(subject_codes),
                Subject.school_id == req.school_id,
            ).distinct()
        )
        valid_codes = set(result.scalars().all())
        invalid = set(subject_codes) - valid_codes
        if invalid:
            raise HTTPException(
                422,
                f"Subject codes not in target school: {sorted(invalid)}",
            )

    # 构造 scope_override — 仅接受 list 或 None，拒绝畸形值
    def _clean_scope(field_name, val):
        if val is None or isinstance(val, list):
            return val
        raise HTTPException(422, f"Scope field '{field_name}' must be a list or null")

    scope_override = {
        "class_ids": _clean_scope("class_ids", req.scope.get("class_ids")),
        "subject_codes": _clean_scope("subject_codes", req.scope.get("subject_codes")),
        "grade_ids": _clean_scope("grade_ids", req.scope.get("grade_ids")),
    }

    token = create_impersonation_token(
        impersonator_id=user.id,
        effective_role=req.role,
        effective_school_id=req.school_id,
        scope_override=scope_override,
    )

    logger.info(
        "impersonate: admin=%s -> role=%s school=%s",
        user.username, req.role, school.name,
    )
    business_event(
        "impersonate_start", "user", user.id,
        effective_role=req.role, school_id=req.school_id,
        scope=scope_override,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "is_impersonation": True,
        "effective_role": req.role,
        "effective_school_id": req.school_id,
        "effective_school_name": school.name,
        "scope": scope_override,
    }


@router.post("/impersonate/exit")
async def exit_impersonation(
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """退出角色模拟，恢复 platform_admin 身份。"""
    impersonator_id = current.get("impersonator_id") or current["user"].id

    # 查找用户的 platform_admin 主角色
    from edu_cloud.models.user_role import UserRole
    result = await db.execute(
        select(UserRole).where(
            UserRole.user_id == impersonator_id,
            UserRole.role.in_(["platform_admin", "admin"]),
        )
    )
    admin_role = result.scalars().first()
    if not admin_role:
        raise HTTPException(403, "Cannot exit: no admin role found")

    token = create_access_token({
        "sub": impersonator_id,
        "role": admin_role.role,
        "active_role_id": admin_role.id,
        **({"school_id": admin_role.school_id} if admin_role.school_id else {}),
    })

    logger.info("impersonate_exit: admin=%s", impersonator_id)
    business_event("impersonate_exit", "user", impersonator_id)

    return {
        "access_token": token,
        "token_type": "bearer",
    }
