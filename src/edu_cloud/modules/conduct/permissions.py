"""Conduct 权限检查辅助函数 + 班级作用域守卫（F002）。"""
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.core.auth import require_permission
from edu_cloud.api.permissions import get_visible_class_ids
from edu_cloud.core.permissions import Permission
from edu_cloud.modules.conduct.models import ConductRuleCategory, ConductRuleItem
from edu_cloud.services.conduct_workflow import Student


def require_view_conduct():
    return Depends(require_permission(Permission.VIEW_CONDUCT))


def require_manage_conduct():
    return Depends(require_permission(Permission.MANAGE_CONDUCT))


def require_manage_rules():
    return Depends(require_permission(Permission.MANAGE_CONDUCT_RULES))


def require_manage_parents():
    return Depends(require_permission(Permission.MANAGE_CONDUCT_PARENTS))


def require_export_conduct():
    return Depends(require_permission(Permission.EXPORT_CONDUCT))


# ── F002: class-scope 守卫 ──

def check_class_scope(current_user: dict, class_id: str) -> None:
    """校验 class_id 是否在当前角色的可见班级列表中。

    校级以上角色（platform_admin/district_admin/principal/academic_director）
    get_visible_class_ids 返回 None（全部可见），直接放行。

    Raises:
        HTTPException 403: 班级不在可见范围
    """
    role = current_user.get("current_role")
    if role is None:
        raise HTTPException(403, "No active role")
    visible = get_visible_class_ids(role)
    if visible is None:
        return  # 全部可见
    if class_id not in visible:
        raise HTTPException(403, f"class '{class_id}' not in your visible scope")


async def check_resource_class(
    db: AsyncSession,
    model,
    resource_id: str,
    expected_class_id: str,
    class_id_path: str = "class_id",
) -> object:
    """校验资源（rule_category/rule_item/group/semester/record）
    的 class_id 等于路径中的 class_id。

    Args:
        model: ORM 模型
        resource_id: 资源 ID
        expected_class_id: 路径里的 class_id
        class_id_path: 如何从资源获取 class_id（可能嵌套）

    Returns: 资源对象（已验证归属）
    Raises: HTTPException 404 (资源不存在) / 403 (跨班)
    """
    result = (await db.execute(select(model).where(model.id == resource_id))).scalar_one_or_none()
    if result is None:
        raise HTTPException(404, f"{model.__name__} '{resource_id}' not found")
    actual = getattr(result, class_id_path, None)
    if actual is None or actual != expected_class_id:
        # 不暴露"存在但不属于本班"，统一返回 404 避免信息泄漏
        raise HTTPException(404, f"{model.__name__} '{resource_id}' not found in class '{expected_class_id}'")
    return result


# ── F002 Round 3: body-field / batch-write 跨班校验 ──

async def check_rule_item_class(
    db: AsyncSession,
    rule_item_id: str,
    class_id: str,
) -> object:
    """校验 rule_item 属本班或属本班所在学校的校级规则。

    合并 rule_item 存在性与归属为单一 join 查询。
    F-004: School-scope rule items (category.scope == "school") cascade into class view,
    so we accept items where category.school_id matches the class's school_id.

    Raises: HTTPException 404 (rule_item 不存在 或 不属于本班/本校)
    """
    from edu_cloud.services.conduct_workflow import Class
    from sqlalchemy import or_

    # Look up the class's school_id for school-scope rule matching
    cls = (await db.execute(select(Class).where(Class.id == class_id))).scalar_one_or_none()
    school_id = cls.school_id if cls else None

    # Match: class-scope item belonging to this class, OR school-scope item belonging to this school
    scope_filters = [ConductRuleCategory.class_id == class_id]
    if school_id:
        scope_filters.append(
            (ConductRuleCategory.scope == "school")
            & (ConductRuleCategory.school_id == school_id)
        )

    stmt = (
        select(ConductRuleItem)
        .join(ConductRuleCategory, ConductRuleItem.category_id == ConductRuleCategory.id)
        .where(
            ConductRuleItem.id == rule_item_id,
            or_(*scope_filters),
        )
    )
    result = (await db.execute(stmt)).scalar_one_or_none()
    if result is None:
        raise HTTPException(
            404,
            f"ConductRuleItem '{rule_item_id}' not found in class '{class_id}'",
        )
    return result


async def check_students_class(
    db: AsyncSession,
    student_ids: list[str],
    class_id: str,
) -> None:
    """批量校验 students 都属本班。空列表 silently return（空操作非越权）。

    单条未匹配（不存在 或 属外班）整体 raise 404，
    不 silently 过滤——静默忽略等同软性 success，违反越权检测语义。

    Raises: HTTPException 404 (任一 student 不存在 或 属外班)
    """
    if not student_ids:
        return
    stmt = select(Student.id).where(
        Student.id.in_(student_ids),
        Student.class_id == class_id,
    )
    found = set((await db.execute(stmt)).scalars().all())
    missing = [sid for sid in student_ids if sid not in found]
    if missing:
        raise HTTPException(
            404,
            f"Students {missing} not found in class '{class_id}'",
        )
