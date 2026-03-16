"""平台级 RBAC：基于角色的权限策略。"""

from enum import Enum


class Permission(str, Enum):
    # 学校管理
    MANAGE_SCHOOLS = "manage_schools"
    VIEW_SCHOOLS = "view_schools"

    # 联考管理
    CREATE_JOINT_EXAM = "create_joint_exam"
    MANAGE_JOINT_EXAM = "manage_joint_exam"
    VIEW_JOINT_EXAM = "view_joint_exam"

    # 跨校分析
    VIEW_CROSS_SCHOOL_ANALYTICS = "view_cross_school_analytics"

    # 题库管理
    MANAGE_QUESTION_BANK = "manage_question_bank"
    VIEW_QUESTION_BANK = "view_question_bank"

    # 平台管理
    MANAGE_USERS = "manage_users"
    MANAGE_PLATFORM = "manage_platform"


ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    "platform_admin": set(Permission),  # 全部权限
    "district_admin": {
        Permission.VIEW_SCHOOLS,
        Permission.CREATE_JOINT_EXAM,
        Permission.MANAGE_JOINT_EXAM,
        Permission.VIEW_JOINT_EXAM,
        Permission.VIEW_CROSS_SCHOOL_ANALYTICS,
        Permission.VIEW_QUESTION_BANK,
    },
    "exam_coordinator": {
        Permission.VIEW_SCHOOLS,
        Permission.CREATE_JOINT_EXAM,
        Permission.MANAGE_JOINT_EXAM,
        Permission.VIEW_JOINT_EXAM,
        Permission.VIEW_QUESTION_BANK,
    },
    "observer": {
        Permission.VIEW_SCHOOLS,
        Permission.VIEW_JOINT_EXAM,
        Permission.VIEW_CROSS_SCHOOL_ANALYTICS,
        Permission.VIEW_QUESTION_BANK,
    },
}


def has_permission(role: str, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())
