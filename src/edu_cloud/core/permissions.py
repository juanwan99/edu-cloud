"""平台级 RBAC：基于角色的权限策略。

角色体系基于中国完全中学双线矩阵管理结构：
  教学线：校长 → 教务主任 → 教研组长 → 备课组长 → 科任教师
  行政线：校长 → 年级组长 → 班主任 → 学生

权限设计原则：
  - 校长 >= 教务主任（查看权限），校长偏审批/配置，教务偏日常运营
  - 教务主任拥有考试/排课/阅卷全生命周期管理权
  - 学校配置（人事/模块/能力矩阵）归校长，教学调度（排课/选考）归教务
  - 教师基线权限一致（班主任 = 科任 + 通知 + 班级管理）
"""

from enum import Enum


class Permission(str, Enum):
    # ── 学校管理 ──
    MANAGE_SCHOOLS = "manage_schools"           # 创建/停用学校（平台/区级）
    VIEW_SCHOOLS = "view_schools"               # 查看学校列表

    # 学校配置（原 MANAGE_SCHOOL_SETTINGS 拆分）
    MANAGE_SCHOOL_CONFIG = "manage_school_config"   # KV 配置/模块开关/能力矩阵/审计日志 → 校长
    MANAGE_SCHEDULING = "manage_scheduling"         # 排课/选考组合 → 教务主任

    # ── 考试管理 ──
    MANAGE_EXAMS = "manage_exams"               # 校内考试 CRUD → 教务主任
    CREATE_JOINT_EXAM = "create_joint_exam"     # 创建联考
    MANAGE_JOINT_EXAM = "manage_joint_exam"     # 联考生命周期管理
    VIEW_JOINT_EXAM = "view_joint_exam"         # 查看联考

    # ── 跨校分析 ──
    VIEW_CROSS_SCHOOL_ANALYTICS = "view_cross_school_analytics"

    # ── 题库管理 ──
    MANAGE_QUESTION_BANK = "manage_question_bank"
    VIEW_QUESTION_BANK = "view_question_bank"

    # ── 平台管理 ──
    MANAGE_USERS = "manage_users"               # 用户 CRUD（平台/区级）
    MANAGE_PLATFORM = "manage_platform"         # 系统级配置

    # ── 数据查看 ──
    VIEW_STUDENTS = "view_students"
    VIEW_EXAMS = "view_exams"
    VIEW_SCORES = "view_scores"

    # ── Studio / 通知 ──
    GENERATE_REPORT = "generate_report"
    GENERATE_NOTIFICATION = "generate_notification"
    APPROVE_NOTIFICATION = "approve_notification"
    SEND_NOTIFICATION = "send_notification"

    # ── AI ──
    USE_AI_CHAT = "use_ai_chat"

    # ── 论文 ──
    WRITE_PAPER = "write_paper"

    # ── 阅卷管理 ──
    MANAGE_GRADING = "manage_grading"           # 阅卷分配/调度 → 教务
    VIEW_GRADING = "view_grading"               # 查看阅卷进度
    MANAGE_EXAM_RESULTS = "manage_exam_results" # 成绩发布/归档/分数段配置

    # ── 作业管理 ──
    MANAGE_HOMEWORK = "manage_homework"
    VIEW_HOMEWORK = "view_homework"

    # ── 知识图谱 ──
    VIEW_KNOWLEDGE_TREE = "view_knowledge_tree"
    EDIT_KNOWLEDGE_TREE = "edit_knowledge_tree"

    # ── 德育（Conduct） ──
    VIEW_CONDUCT = "view_conduct"
    MANAGE_CONDUCT = "manage_conduct"
    MANAGE_CONDUCT_RULES = "manage_conduct_rules"
    MANAGE_CONDUCT_PARENTS = "manage_conduct_parents"
    EXPORT_CONDUCT = "export_conduct"


# ── 教师基线权限（班主任和科任教师共享的教学权限） ──
_TEACHER_BASE: set[Permission] = {
    Permission.VIEW_STUDENTS,
    Permission.VIEW_EXAMS,
    Permission.VIEW_SCORES,
    Permission.VIEW_QUESTION_BANK,
    Permission.VIEW_GRADING,
    Permission.MANAGE_GRADING,
    Permission.VIEW_HOMEWORK,
    Permission.MANAGE_HOMEWORK,
    Permission.GENERATE_REPORT,
    Permission.USE_AI_CHAT,
    Permission.WRITE_PAPER,
    Permission.VIEW_KNOWLEDGE_TREE,
    Permission.EDIT_KNOWLEDGE_TREE,
    Permission.VIEW_CONDUCT,
    Permission.MANAGE_CONDUCT,
}


ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    # ── 平台超管 — 全部权限 ──
    "platform_admin": set(Permission),

    # ── 区管理员 ──
    "district_admin": {
        Permission.MANAGE_SCHOOLS,
        Permission.VIEW_SCHOOLS,
        Permission.MANAGE_SCHOOL_CONFIG,
        Permission.MANAGE_SCHEDULING,
        Permission.MANAGE_EXAMS,
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
        Permission.MANAGE_GRADING,
        Permission.VIEW_GRADING,
        Permission.MANAGE_EXAM_RESULTS,
        Permission.MANAGE_HOMEWORK,
        Permission.VIEW_HOMEWORK,
        Permission.VIEW_KNOWLEDGE_TREE,
        Permission.EDIT_KNOWLEDGE_TREE,
        Permission.VIEW_CONDUCT,
        Permission.MANAGE_CONDUCT,
        Permission.MANAGE_CONDUCT_RULES,
        Permission.MANAGE_CONDUCT_PARENTS,
        Permission.EXPORT_CONDUCT,
    },

    # ── 校长：全校最高管理者，查看 >= 教务，偏审批/配置 ──
    "principal": {
        Permission.VIEW_SCHOOLS,
        Permission.MANAGE_SCHOOL_CONFIG,     # 学校配置/模块/能力矩阵 → 校长职责
        Permission.MANAGE_SCHEDULING,        # 校长可管排课（通常委托教务，但有权限）
        Permission.MANAGE_EXAMS,             # 可创建考试（通常委托教务）
        Permission.CREATE_JOINT_EXAM,        # 联考决策需校长参与
        Permission.MANAGE_JOINT_EXAM,        # 联考管理
        Permission.VIEW_JOINT_EXAM,
        Permission.VIEW_CROSS_SCHOOL_ANALYTICS,
        Permission.VIEW_QUESTION_BANK,
        Permission.VIEW_STUDENTS,
        Permission.VIEW_EXAMS,
        Permission.VIEW_SCORES,
        Permission.GENERATE_REPORT,
        Permission.APPROVE_NOTIFICATION,     # 通知审批
        Permission.SEND_NOTIFICATION,
        Permission.GENERATE_NOTIFICATION,
        Permission.USE_AI_CHAT,
        Permission.MANAGE_GRADING,           # 可查看/管理阅卷调度
        Permission.VIEW_GRADING,
        Permission.MANAGE_EXAM_RESULTS,      # 成绩发布审批
        Permission.MANAGE_HOMEWORK,          # 可查看全校作业
        Permission.VIEW_HOMEWORK,
        Permission.VIEW_KNOWLEDGE_TREE,
        Permission.EDIT_KNOWLEDGE_TREE,
        Permission.VIEW_CONDUCT,
        Permission.EXPORT_CONDUCT,
    },

    # ── 教务主任：教学运营管理者，考试/排课/阅卷全生命周期 ──
    "academic_director": {
        Permission.VIEW_SCHOOLS,
        Permission.MANAGE_SCHEDULING,        # 排课/选考组合 → 教务核心职责
        Permission.MANAGE_EXAMS,             # 校内考试 CRUD
        Permission.CREATE_JOINT_EXAM,
        Permission.MANAGE_JOINT_EXAM,
        Permission.VIEW_JOINT_EXAM,
        Permission.VIEW_CROSS_SCHOOL_ANALYTICS,  # 教务也需联考数据对比
        Permission.MANAGE_QUESTION_BANK,     # 学科题库管理
        Permission.VIEW_QUESTION_BANK,
        Permission.VIEW_STUDENTS,
        Permission.VIEW_EXAMS,
        Permission.VIEW_SCORES,
        Permission.GENERATE_REPORT,
        Permission.GENERATE_NOTIFICATION,
        Permission.SEND_NOTIFICATION,
        Permission.USE_AI_CHAT,
        Permission.MANAGE_GRADING,           # 阅卷分配/调度
        Permission.VIEW_GRADING,
        Permission.MANAGE_EXAM_RESULTS,      # 成绩发布/分数段配置
        Permission.MANAGE_HOMEWORK,          # 全校作业质量监控
        Permission.VIEW_HOMEWORK,
        Permission.VIEW_KNOWLEDGE_TREE,
        Permission.EDIT_KNOWLEDGE_TREE,
        Permission.VIEW_CONDUCT,
        Permission.MANAGE_CONDUCT,
        Permission.MANAGE_CONDUCT_RULES,
        Permission.EXPORT_CONDUCT,
    },

    # ── 教研组长：跨年级单学科教研负责人 ──
    # 作用域：全校 · 单学科 · 全班级（由 DataScope 控制）
    "teaching_research_leader": {
        Permission.VIEW_STUDENTS,
        Permission.VIEW_EXAMS,
        Permission.VIEW_SCORES,
        Permission.VIEW_QUESTION_BANK,
        Permission.VIEW_GRADING,
        Permission.VIEW_HOMEWORK,
        Permission.GENERATE_REPORT,          # 学科分析报告
        Permission.USE_AI_CHAT,
        Permission.WRITE_PAPER,
        Permission.VIEW_KNOWLEDGE_TREE,
        Permission.EDIT_KNOWLEDGE_TREE,      # 学科知识体系维护
    },

    # ── 年级组长：单年级行政管理者 ──
    # 作用域：单年级 · 全科 · 全班级（由 DataScope 控制）
    "grade_leader": {
        Permission.VIEW_STUDENTS,
        Permission.VIEW_EXAMS,
        Permission.VIEW_SCORES,
        Permission.VIEW_JOINT_EXAM,
        Permission.VIEW_QUESTION_BANK,       # 组织年级统考需看题库
        Permission.GENERATE_REPORT,
        Permission.GENERATE_NOTIFICATION,
        Permission.SEND_NOTIFICATION,        # 给本年级家长发通知
        Permission.USE_AI_CHAT,
        Permission.VIEW_GRADING,
        Permission.VIEW_HOMEWORK,
        Permission.VIEW_KNOWLEDGE_TREE,
        Permission.VIEW_CONDUCT,
        Permission.MANAGE_CONDUCT,
        Permission.EXPORT_CONDUCT,
    },

    # ── 备课组长：单年级单学科全平行班教研协调 ──
    # 作用域：单年级 · 单学科 · 该年级全部平行班（由 DataScope 控制）
    # 基于教师基线，不额外加权限
    # 与科任教师的区别在 DataScope：能看到本年级所有平行班（不限于自己带的班）
    "lesson_prep_leader": _TEACHER_BASE | {
        Permission.MANAGE_GRADING,
        Permission.MANAGE_EXAMS,
    },

    # ── 班主任：教师基线 + 班级通知管理 ──
    # 作用域：本班全科 + 任教班本科（由 DataScope 控制）
    "homeroom_teacher": _TEACHER_BASE | {
        Permission.GENERATE_NOTIFICATION,    # 给班级家长发通知
        Permission.SEND_NOTIFICATION,
        Permission.MANAGE_CONDUCT_RULES,
        Permission.MANAGE_CONDUCT_PARENTS,
        Permission.EXPORT_CONDUCT,
    },

    # ── 科任教师：教师基线 ──
    # 作用域：任教班 · 任教科（由 DataScope 控制）
    "subject_teacher": _TEACHER_BASE.copy(),

    # ── 家长 ──
    "parent": {
        Permission.VIEW_SCORES,
        Permission.VIEW_HOMEWORK,
        Permission.USE_AI_CHAT,
        Permission.VIEW_KNOWLEDGE_TREE,
        Permission.VIEW_CONDUCT,
    },

    # ── 旧角色兼容（exam-ai 迁入） ──
    "admin": set(Permission),
    "teacher": _TEACHER_BASE.copy(),
    "head_teacher": _TEACHER_BASE | {
        Permission.GENERATE_NOTIFICATION,
        Permission.SEND_NOTIFICATION,
        Permission.MANAGE_CONDUCT_RULES,
        Permission.MANAGE_CONDUCT_PARENTS,
        Permission.EXPORT_CONDUCT,
    },

    "exam_coordinator": {
        Permission.VIEW_SCHOOLS,
        Permission.MANAGE_EXAMS,
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
