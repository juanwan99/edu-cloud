"""模拟登录权限测试 — 验证模拟继承目标角色完整权限。"""
from edu_cloud.core.permissions import Permission, ROLE_PERMISSIONS


IMPERSONATABLE_ROLES = [
    "principal",
    "academic_director",
    "teaching_research_leader",
    "grade_leader",
    "lesson_prep_leader",
    "homeroom_teacher",
    "subject_teacher",
]


def test_impersonation_grants_full_role_permissions():
    """模拟登录继承目标角色的完整权限。"""
    for role in IMPERSONATABLE_ROLES:
        perms = ROLE_PERMISSIONS.get(role, set())
        assert len(perms) > 0, f"{role} should have permissions"


def test_impersonated_academic_director_has_manage_grading():
    """模拟 academic_director 后保留 MANAGE_GRADING（修复 403 回归）。"""
    perms = ROLE_PERMISSIONS.get("academic_director", set())
    assert Permission.MANAGE_GRADING in perms
    assert Permission.VIEW_GRADING in perms
    assert Permission.VIEW_SCORES in perms


def test_impersonatable_roles_exclude_platform_admin():
    """平台管理员不可被模拟（防止权限提升）。"""
    assert "platform_admin" not in IMPERSONATABLE_ROLES
    assert "admin" not in IMPERSONATABLE_ROLES
