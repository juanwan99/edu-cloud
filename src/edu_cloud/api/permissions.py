"""数据权限过滤：根据用户角色限制可见的班级和学科。

适配 edu-cloud 的 UserRole 模型（exam-ai 原版基于 User.role 单角色）。
"""


SCHOOL_ADMIN_ROLES = frozenset({
    "platform_admin", "district_admin", "principal", "academic_director",
    "admin",  # legacy alias for platform_admin
})


def is_school_admin(role) -> bool:
    """角色是否有校级管理权限（阅卷分配、查看全部分配等）。"""
    return role.role in SCHOOL_ADMIN_ROLES


def get_visible_class_ids(role) -> list[str] | None:
    """返回角色可见的班级 ID 列表，None = 全部可见。"""
    if role.role in ("platform_admin", "district_admin", "principal", "academic_director", "admin"):
        return None
    return role.class_ids or []


def get_visible_subject_codes(role) -> list[str] | None:
    """返回角色可见的学科代码列表，None = 全部可见。"""
    if role.role in ("platform_admin", "district_admin", "principal",
                     "academic_director", "homeroom_teacher", "admin",
                     "head_teacher"):
        return None
    return role.subject_codes or []
