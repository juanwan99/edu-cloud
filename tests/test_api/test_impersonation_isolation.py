"""模拟登录权限隔离测试。"""
import pytest
from edu_cloud.core.permissions import Permission, ROLE_PERMISSIONS
from edu_cloud.api.deps import _IMPERSONATION_BLOCKED_PERMISSIONS


def test_impersonation_blocked_permissions_are_write_only():
    """blocked set 只包含写权限，不包含查看权限。"""
    for p in _IMPERSONATION_BLOCKED_PERMISSIONS:
        assert "manage" in p.value or "create" in p.value, f"{p} is not a write permission"


def test_impersonation_still_has_view_permissions():
    """模拟后仍应保留查看权限。"""
    full = ROLE_PERMISSIONS.get("academic_director", set())
    safe = full - _IMPERSONATION_BLOCKED_PERMISSIONS
    assert len(safe) > 0, "Impersonation should retain some permissions"
    assert Permission.VIEW_SCORES in safe or Permission.VIEW_GRADING in safe


def test_impersonation_no_write_permissions():
    """模拟后不应有写权限。"""
    full = ROLE_PERMISSIONS.get("principal", set())
    safe = full - _IMPERSONATION_BLOCKED_PERMISSIONS
    assert safe & _IMPERSONATION_BLOCKED_PERMISSIONS == set()
