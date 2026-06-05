"""有序路由注册表 — 替代 app.py 中的手工 import 堆砌。

平台路由（auth/ai/dashboard 等）和模块路由分开声明。
每个条目 = (import_path, attr_name)，顺序决定注册顺序。
"""
import importlib
import logging

from fastapi import FastAPI

logger = logging.getLogger(__name__)

# (import_path, attr_name) — prefix/tags 已在各 router 文件中定义
PLATFORM_ROUTERS: list[tuple[str, str]] = [
    ("edu_cloud.api.auth", "router"),
    ("edu_cloud.api.impersonate", "router"),
    ("edu_cloud.api.client_logs", "router"),
    ("edu_cloud.api.dashboard", "router"),
    ("edu_cloud.api.ai", "router"),
    ("edu_cloud.api.compat_router", "router"),
]

# 顺序与 app.py:387-396 for-loop 完全一致
MODULE_ROUTERS: list[tuple[str, str]] = [
    # school
    ("edu_cloud.modules.school.router", "router"),
    ("edu_cloud.modules.school.settings_router", "router"),
    ("edu_cloud.modules.school.assignment_router", "router"),
    ("edu_cloud.modules.school.selection_router", "router"),
    ("edu_cloud.modules.school.capability_router", "router"),
    ("edu_cloud.modules.school.audit_router", "router"),
    # homework
    ("edu_cloud.modules.homework.router", "router"),
    # exam
    ("edu_cloud.modules.exam.router", "router"),
    ("edu_cloud.modules.exam.router", "question_router"),
    ("edu_cloud.modules.exam.joint_exam_router", "router"),
    ("edu_cloud.modules.exam.results_router", "router"),
    ("edu_cloud.modules.exam.workspace_router", "router"),
    ("edu_cloud.modules.exam.llm_config_router", "router"),
    # student
    ("edu_cloud.modules.student.router", "router"),
    # card
    ("edu_cloud.modules.card.router", "router"),
    ("edu_cloud.modules.card.template_router", "router"),
    # scan
    ("edu_cloud.modules.scan.router", "router"),
    # grading
    ("edu_cloud.modules.grading.router", "router"),
    # marking
    ("edu_cloud.modules.marking.router", "router"),
    # analytics
    ("edu_cloud.modules.analytics.router", "router"),
    # knowledge
    ("edu_cloud.modules.knowledge.router", "router"),
    # pipeline
    ("edu_cloud.modules.pipeline.router", "router"),
    # studio
    ("edu_cloud.modules.studio.router", "router"),
    # calendar
    ("edu_cloud.modules.calendar.router", "router"),
    # notifications (platform-level but module-scoped)
    ("edu_cloud.api.notifications_api", "router"),
    # grading (continued)
    ("edu_cloud.modules.grading.assignment_router", "router"),
    ("edu_cloud.modules.grading.quality_router", "router"),
    # profile
    ("edu_cloud.modules.profile.router", "router"),
    # bank
    ("edu_cloud.modules.bank.router", "router"),
    # knowledge_tree
    ("edu_cloud.modules.knowledge_tree.router", "router"),
    # scan (continued)
    ("edu_cloud.modules.scan.pipeline_router", "router"),
    ("edu_cloud.modules.scan.cv_detect_router", "router"),
    # conduct
    ("edu_cloud.modules.conduct.parent_router", "router"),
    ("edu_cloud.modules.conduct.admin_router", "router"),
    ("edu_cloud.modules.conduct.notification_router", "router"),
    # menu
    ("edu_cloud.modules.menu.router", "router"),
    # student (continued)
    ("edu_cloud.modules.student.teacher_router", "router"),
    # academic
    ("edu_cloud.modules.academic.router", "router"),
    # exam-import
    ("edu_cloud.modules.exam_import.router", "router"),
    # portal
    ("edu_cloud.modules.portal.router", "router"),
]


def register_all(app: FastAPI) -> None:
    """Import and register all routers onto the FastAPI app."""
    for import_path, attr in PLATFORM_ROUTERS + MODULE_ROUTERS:
        mod = importlib.import_module(import_path)
        router = getattr(mod, attr)
        app.include_router(router)
        logger.debug("Registered %s.%s -> %s", import_path, attr, router.prefix)
