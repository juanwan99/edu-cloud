"""数据权限过滤：根据用户角色限制可见的班级、年级和学科。

适配 edu-cloud 的 UserRole 模型（exam-ai 原版基于 User.role 单角色）。
"""

from sqlalchemy import String, cast, false, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.student.models import Class


SCHOOL_ADMIN_ROLES = frozenset({
    "platform_admin", "district_admin", "school_admin", "principal", "academic_director",
    "admin",  # legacy alias for platform_admin
})

GRADE_SCOPED_ROLES = frozenset({"grade_leader", "lesson_prep_leader"})


def is_school_admin(role) -> bool:
    """角色是否有校级管理权限（阅卷分配、查看全部分配等）。"""
    return role.role in SCHOOL_ADMIN_ROLES


def get_visible_class_ids(role) -> list[str] | None:
    """返回角色可见的班级 ID 列表，None = 全部可见。"""
    if role.role in ("platform_admin", "district_admin", "school_admin", "principal", "academic_director", "admin"):
        return None
    return role.class_ids or []



def get_visible_grade_ids(role) -> list[str] | None:
    """返回角色可见的年级 ID/编号列表，None = 不按年级限制。"""
    if role.role in GRADE_SCOPED_ROLES:
        return role.grade_ids or []
    return None


def grade_predicate(model, grade_ids: list[str]):
    """匹配系统内并存的 grade_id、grade_number、grade 文本字段。"""
    if not grade_ids:
        return false()
    values = [str(g) for g in grade_ids]
    clauses = []
    if hasattr(model, "grade_id"):
        clauses.append(model.grade_id.in_(values))
    if hasattr(model, "grade_number"):
        clauses.append(cast(model.grade_number, String).in_(values))
    if hasattr(model, "grade"):
        clauses.append(model.grade.in_(values))
    return or_(*clauses) if clauses else false()


async def resolve_visible_class_ids(db: AsyncSession, role) -> list[str] | None:
    """返回可直接用于 class_id 过滤的班级 ID，支持 grade_ids 解析。"""
    visible_class_ids = get_visible_class_ids(role)
    visible_grade_ids = get_visible_grade_ids(role)
    if visible_grade_ids is None:
        return visible_class_ids
    if not visible_grade_ids:
        return visible_class_ids or []

    stmt = select(Class.id).where(Class.school_id == role.school_id)
    stmt = stmt.where(grade_predicate(Class, visible_grade_ids))
    if visible_class_ids:
        stmt = stmt.where(Class.id.in_(visible_class_ids))
    result = await db.execute(stmt)
    return list(result.scalars().all())


def get_visible_subject_codes(role) -> list[str] | None:
    """返回角色可见的学科代码列表，None = 全部可见。"""
    if role.role in ("platform_admin", "district_admin", "school_admin", "principal",
                     "academic_director", "grade_leader", "homeroom_teacher", "admin",
                     "head_teacher"):
        return None
    return role.subject_codes or []
