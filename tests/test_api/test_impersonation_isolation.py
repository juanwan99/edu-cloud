"""模拟登录权限隔离测试。"""
from edu_cloud.core.permissions import Permission, ROLE_PERMISSIONS
from edu_cloud.api.deps import _IMPERSONATION_ALLOWED_PERMISSIONS


def test_impersonation_allowed_are_read_only():
    """allowlist 只包含查看/消费类权限。"""
    for p in _IMPERSONATION_ALLOWED_PERMISSIONS:
        assert (
            "view" in p.value or "use" in p.value or p == Permission.GENERATE_REPORT
        ), f"{p} should be read-only"


def test_impersonation_retains_view_permissions():
    """模拟 academic_director 后仍保留查看权限。"""
    full = ROLE_PERMISSIONS.get("academic_director", set())
    safe = full & _IMPERSONATION_ALLOWED_PERMISSIONS
    assert len(safe) > 0
    assert Permission.VIEW_SCORES in safe
    assert Permission.VIEW_GRADING in safe


def test_impersonation_strips_all_write_permissions():
    """模拟后不应有任何写权限（MANAGE/CREATE/EDIT/WRITE/SEND/APPROVE）。"""
    full = ROLE_PERMISSIONS.get("principal", set())
    safe = full & _IMPERSONATION_ALLOWED_PERMISSIONS
    write_keywords = {"manage", "create", "edit", "write", "send", "approve", "export"}
    leaked = {p for p in safe if any(k in p.value for k in write_keywords)}
    assert leaked == set(), f"Write permissions leaked: {leaked}"


def test_impersonation_no_manage_users():
    """F-02 回归：模拟登录绝不能有 MANAGE_USERS。"""
    full = ROLE_PERMISSIONS.get("platform_admin", set())
    safe = full & _IMPERSONATION_ALLOWED_PERMISSIONS
    assert Permission.MANAGE_USERS not in safe
    assert Permission.MANAGE_PLATFORM not in safe
    assert Permission.WRITE_PAPER not in safe
    assert Permission.EDIT_KNOWLEDGE_TREE not in safe
