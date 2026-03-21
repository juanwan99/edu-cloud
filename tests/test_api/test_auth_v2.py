"""RBAC v2 认证测试：多角色 + switch-role + 权限隔离。"""

import pytest


@pytest.mark.asyncio
async def test_login_returns_roles(client, seed_teacher):
    """新 User 登录返回 roles 列表。"""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "teacher1", "password": "123456"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "roles" in data
    assert len(data["roles"]) >= 1
    assert data["roles"][0]["role"] == "homeroom_teacher"


@pytest.mark.asyncio
async def test_permission_denied_for_wrong_role(client, teacher_headers):
    """班主任无 MANAGE_SCHOOLS 权限，创建学校被 403。"""
    resp = await client.post(
        "/api/v1/schools",
        json={"name": "测试校", "code": "DENY01", "district": "测试区"},
        headers=teacher_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_login_returns_roles(client, admin_user):
    """新 User admin 登录也返回 roles。"""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin_test", "password": "test123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "roles" in data
    assert data["roles"][0]["role"] == "platform_admin"
    assert data["user"]["role"] == "platform_admin"


@pytest.mark.asyncio
async def test_switch_role(client, db):
    """多角色用户切换角色后得到新 token。"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole

    user = User(username="multi_role", display_name="多角色用户")
    user.set_password("pass123")
    db.add(user)
    await db.flush()

    role1 = UserRole(user_id=user.id, role="principal", is_primary=True)
    role2 = UserRole(user_id=user.id, role="subject_teacher", is_primary=False)
    db.add_all([role1, role2])
    await db.commit()
    await db.refresh(role1)
    await db.refresh(role2)

    # Login as primary role (principal)
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "multi_role", "password": "pass123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Switch to subject_teacher
    switch_resp = await client.post(
        "/api/v1/auth/switch-role",
        json={"role_id": role2.id},
        headers=headers,
    )
    assert switch_resp.status_code == 200
    assert switch_resp.json()["active_role"]["role"] == "subject_teacher"


@pytest.mark.asyncio
async def test_switch_role_invalid_id(client, admin_user, admin_headers):
    """切换不存在的角色 ID → 404。"""
    resp = await client.post(
        "/api/v1/auth/switch-role",
        json={"role_id": "nonexistent-id"},
        headers=admin_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_login_invalid_credentials(client, seed_teacher):
    """错误密码 → 401。"""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "teacher1", "password": "wrong"},
    )
    assert resp.status_code == 401
