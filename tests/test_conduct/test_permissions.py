"""Conduct 权限测试"""
import pytest
from edu_cloud.core.permissions import Permission, has_permission


def test_conduct_permissions_exist():
    """5 个 conduct 权限存在"""
    assert Permission.VIEW_CONDUCT
    assert Permission.MANAGE_CONDUCT
    assert Permission.MANAGE_CONDUCT_RULES
    assert Permission.MANAGE_CONDUCT_PARENTS
    assert Permission.EXPORT_CONDUCT


def test_homeroom_teacher_has_all_conduct_perms():
    assert has_permission("homeroom_teacher", Permission.VIEW_CONDUCT)
    assert has_permission("homeroom_teacher", Permission.MANAGE_CONDUCT)
    assert has_permission("homeroom_teacher", Permission.MANAGE_CONDUCT_RULES)
    assert has_permission("homeroom_teacher", Permission.MANAGE_CONDUCT_PARENTS)
    assert has_permission("homeroom_teacher", Permission.EXPORT_CONDUCT)


def test_subject_teacher_has_view_and_manage():
    assert has_permission("subject_teacher", Permission.VIEW_CONDUCT)
    assert has_permission("subject_teacher", Permission.MANAGE_CONDUCT)
    assert not has_permission("subject_teacher", Permission.MANAGE_CONDUCT_RULES)
    assert not has_permission("subject_teacher", Permission.MANAGE_CONDUCT_PARENTS)


def test_parent_has_view_only():
    assert has_permission("parent", Permission.VIEW_CONDUCT)
    assert not has_permission("parent", Permission.MANAGE_CONDUCT)


def test_grade_leader_has_view_manage_export():
    assert has_permission("grade_leader", Permission.VIEW_CONDUCT)
    assert has_permission("grade_leader", Permission.MANAGE_CONDUCT)
    assert has_permission("grade_leader", Permission.EXPORT_CONDUCT)
    assert not has_permission("grade_leader", Permission.MANAGE_CONDUCT_PARENTS)


# ── T1 (2026-04-14): lesson_prep_leader conduct 权限回收 ──

def test_lesson_prep_leader_no_view_conduct():
    from edu_cloud.core.permissions import has_permission, Permission
    assert has_permission("lesson_prep_leader", Permission.VIEW_CONDUCT) is False


def test_lesson_prep_leader_no_manage_conduct():
    from edu_cloud.core.permissions import has_permission, Permission
    assert has_permission("lesson_prep_leader", Permission.MANAGE_CONDUCT) is False


def test_subject_teacher_still_has_conduct():
    from edu_cloud.core.permissions import has_permission, Permission
    assert has_permission("subject_teacher", Permission.VIEW_CONDUCT) is True
    assert has_permission("subject_teacher", Permission.MANAGE_CONDUCT) is True


def test_homeroom_teacher_still_has_conduct():
    from edu_cloud.core.permissions import has_permission, Permission
    assert has_permission("homeroom_teacher", Permission.VIEW_CONDUCT) is True
    assert has_permission("homeroom_teacher", Permission.MANAGE_CONDUCT) is True
    assert has_permission("homeroom_teacher", Permission.MANAGE_CONDUCT_RULES) is True
