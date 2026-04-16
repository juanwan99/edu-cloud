"""Parent role permission tests."""

from edu_cloud.core.permissions import ROLE_PERMISSIONS, Permission


def test_parent_has_use_ai_chat():
    assert Permission.USE_AI_CHAT in ROLE_PERMISSIONS["parent"]


def test_parent_has_view_scores():
    assert Permission.VIEW_SCORES in ROLE_PERMISSIONS["parent"]


def test_parent_no_write_permissions():
    parent_perms = ROLE_PERMISSIONS["parent"]
    write_perms = {
        Permission.MANAGE_SCHOOLS,
        Permission.MANAGE_HOMEWORK,
        Permission.MANAGE_GRADING,
        Permission.MANAGE_EXAM_RESULTS,
    }
    assert not parent_perms & write_perms
