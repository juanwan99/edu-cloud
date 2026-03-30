from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.capability import Capability, CAPABILITY_DOMAINS, CAPABILITY_ACTIONS
from edu_cloud.services.exceptions import ValidationError


# 默认模板: role → {domain: {action: enabled}}
# platform_admin / district_admin 不生成 capability 行（跳过检查）
DEFAULT_CAPABILITIES: dict[str, dict[str, dict[str, bool]]] = {
    "principal": {
        domain: {"read": True, "write": True}
        for domain in CAPABILITY_DOMAINS
    },
    "academic_director": {
        domain: {
            "read": True,
            "write": True if domain != "system" else False,
        }
        for domain in CAPABILITY_DOMAINS
    },
    "grade_leader": {
        domain: actions
        for domain, actions in [
            ("exam", {"read": True}),
            ("grading", {"read": True}),
            ("study_analytics", {"read": True}),
            ("studio", {"read": True}),
            ("calendar", {"read": True}),
        ]
    },
    "homeroom_teacher": {
        domain: actions
        for domain, actions in [
            ("exam", {"read": True, "write": True}),
            ("grading", {"read": True, "write": True}),
            ("study_analytics", {"read": True}),
            ("calendar", {"read": True}),
            ("studio", {"read": True}),
        ]
    },
    "subject_teacher": {
        domain: actions
        for domain, actions in [
            ("exam", {"read": True, "write": True}),
            ("grading", {"read": True, "write": True}),
            ("study_analytics", {"read": True}),
            ("research", {"read": True}),
        ]
    },
    "parent": {
        "study_analytics": {"read": True},
    },
}


async def init_school_capabilities(
    db: AsyncSession, *, school_id: str,
) -> None:
    """按默认模板批量创建 capability 行（幂等）。"""
    for role, domains in DEFAULT_CAPABILITIES.items():
        for domain, actions in domains.items():
            for action, enabled in actions.items():
                existing = (await db.execute(
                    select(Capability).where(
                        Capability.school_id == school_id,
                        Capability.role == role,
                        Capability.domain == domain,
                        Capability.action == action,
                    )
                )).scalar_one_or_none()
                if not existing:
                    db.add(Capability(
                        school_id=school_id,
                        role=role,
                        domain=domain,
                        action=action,
                        enabled=enabled,
                    ))
    await db.commit()


async def get_capabilities(
    db: AsyncSession, *, school_id: str, role: str | None = None,
) -> list[Capability]:
    stmt = select(Capability).where(Capability.school_id == school_id)
    if role:
        stmt = stmt.where(Capability.role == role)
    result = await db.execute(stmt.order_by(Capability.role, Capability.domain, Capability.action))
    return list(result.scalars().all())


async def set_capability(
    db: AsyncSession, *, school_id: str, role: str,
    domain: str, action: str, enabled: bool,
) -> Capability:
    if domain not in CAPABILITY_DOMAINS:
        raise ValidationError(f"无效的域: {domain}")
    if action not in CAPABILITY_ACTIONS:
        raise ValidationError(f"无效的操作: {action}")
    stmt = select(Capability).where(
        Capability.school_id == school_id,
        Capability.role == role,
        Capability.domain == domain,
        Capability.action == action,
    )
    cap = (await db.execute(stmt)).scalar_one_or_none()
    if cap:
        cap.enabled = enabled
    else:
        cap = Capability(
            school_id=school_id, role=role,
            domain=domain, action=action, enabled=enabled,
        )
        db.add(cap)
    await db.commit()
    await db.refresh(cap)
    return cap


async def check_capability(
    db: AsyncSession, *, school_id: str, role: str,
    domain: str, action: str,
) -> bool:
    """检查角色在指定域的操作权限。无记录 = 默认允许（宽松策略）。"""
    stmt = select(Capability).where(
        Capability.school_id == school_id,
        Capability.role == role,
        Capability.domain == domain,
        Capability.action == action,
    )
    cap = (await db.execute(stmt)).scalar_one_or_none()
    if cap is None:
        return True  # 宽松策略：无记录默认允许
    return cap.enabled
