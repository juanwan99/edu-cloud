"""平台级 RBAC：基于角色的权限策略。"""

from enum import Enum


class Permission(str, Enum):
    # 学校管理（既有）
    MANAGE_SCHOOLS = "manage_schools"
    VIEW_SCHOOLS = "view_schools"

    # 联考管理（既有）
    CREATE_JOINT_EXAM = "create_joint_exam"
    MANAGE_JOINT_EXAM = "manage_joint_exam"
    VIEW_JOINT_EXAM = "view_joint_exam"

    # 跨校分析（既有）
    VIEW_CROSS_SCHOOL_ANALYTICS = "view_cross_school_analytics"

    # 题库管理（既有）
    MANAGE_QUESTION_BANK = "manage_question_bank"
    VIEW_QUESTION_BANK = "view_question_bank"

    # 平台管理（既有）
    MANAGE_USERS = "manage_users"
    MANAGE_PLATFORM = "manage_platform"

    # 数据查看（新增）
    VIEW_STUDENTS = "view_students"
    VIEW_EXAMS = "view_exams"
    VIEW_SCORES = "view_scores"

    # Studio（P2，新增）
    GENERATE_REPORT = "generate_report"
    GENERATE_NOTIFICATION = "generate_notification"
    APPROVE_NOTIFICATION = "approve_notification"
    SEND_NOTIFICATION = "send_notification"

    # AI（P1，新增）
    USE_AI_CHAT = "use_ai_chat"

    # 论文（P4，新增）
    WRITE_PAPER = "write_paper"


ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    # 平台超管 — 全部权限
    "platform_admin": set(Permission),

    # 区管理员
    "district_admin": {
        Permission.MANAGE_SCHOOLS,
        Permission.VIEW_SCHOOLS,
        Permission.CREATE_JOINT_EXAM,
        Permission.MANAGE_JOINT_EXAM,
        Permission.VIEW_JOINT_EXAM,
        Permission.VIEW_CROSS_SCHOOL_ANALYTICS,
        Permission.VIEW_QUESTION_BANK,
        Permission.MANAGE_USERS,
        Permission.VIEW_STUDENTS,
        Permission.VIEW_EXAMS,
        Permission.VIEW_SCORES,
        Permission.GENERATE_REPORT,
        Permission.APPROVE_NOTIFICATION,
        Permission.SEND_NOTIFICATION,
        Permission.GENERATE_NOTIFICATION,
        Permission.USE_AI_CHAT,
    },

    # 校长
    "principal": {
        Permission.VIEW_SCHOOLS,
        Permission.VIEW_JOINT_EXAM,
        Permission.VIEW_CROSS_SCHOOL_ANALYTICS,
        Permission.VIEW_QUESTION_BANK,
        Permission.VIEW_STUDENTS,
        Permission.VIEW_EXAMS,
        Permission.VIEW_SCORES,
        Permission.GENERATE_REPORT,
        Permission.APPROVE_NOTIFICATION,
        Permission.SEND_NOTIFICATION,
        Permission.GENERATE_NOTIFICATION,
        Permission.USE_AI_CHAT,
    },

    # 教务主任
    "academic_director": {
        Permission.VIEW_SCHOOLS,
        Permission.CREATE_JOINT_EXAM,
        Permission.MANAGE_JOINT_EXAM,
        Permission.VIEW_JOINT_EXAM,
        Permission.VIEW_QUESTION_BANK,
        Permission.VIEW_STUDENTS,
        Permission.VIEW_EXAMS,
        Permission.VIEW_SCORES,
        Permission.GENERATE_REPORT,
        Permission.GENERATE_NOTIFICATION,
        Permission.SEND_NOTIFICATION,
        Permission.USE_AI_CHAT,
    },

    # 年级组长
    "grade_leader": {
        Permission.VIEW_STUDENTS,
        Permission.VIEW_EXAMS,
        Permission.VIEW_SCORES,
        Permission.VIEW_JOINT_EXAM,
        Permission.GENERATE_REPORT,
        Permission.GENERATE_NOTIFICATION,
        Permission.USE_AI_CHAT,
    },

    # 班主任
    "homeroom_teacher": {
        Permission.VIEW_STUDENTS,
        Permission.VIEW_EXAMS,
        Permission.VIEW_SCORES,
        Permission.GENERATE_REPORT,
        Permission.GENERATE_NOTIFICATION,
        Permission.SEND_NOTIFICATION,
        Permission.USE_AI_CHAT,
    },

    # 科任教师
    "subject_teacher": {
        Permission.VIEW_STUDENTS,
        Permission.VIEW_EXAMS,
        Permission.VIEW_SCORES,
        Permission.VIEW_QUESTION_BANK,
        Permission.USE_AI_CHAT,
        Permission.WRITE_PAPER,
    },

    # 家长
    "parent": {
        Permission.VIEW_SCORES,
    },

    # 旧角色兼容
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
