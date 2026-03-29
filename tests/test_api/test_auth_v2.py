"""RBAC v2 认证测试：多角色 + switch-role + 权限隔离。"""

import pytest
from edu_cloud.shared.auth import decode_token


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


@pytest.mark.asyncio
async def test_login_nonexistent_user(client):
    """不存在的用户 → 401。"""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "nobody_exists", "password": "any"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_jwt_contains_role_claims(client, seed_teacher):
    """登录返回的 JWT 包含 role 和 active_role_id claim。"""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "teacher1", "password": "123456"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    payload = decode_token(token)
    assert payload["role"] == "homeroom_teacher"
    assert "active_role_id" in payload
    assert payload["sub"]  # user id present


@pytest.mark.asyncio
async def test_switch_role_jwt_and_scope(client, db):
    """switch-role 后新 token 的 claim 更新，且新 token 可正常访问端点。"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.models.school import School

    school = School(name="Scope测试校", code="SCOPE01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    user = User(username="scope_user", display_name="Scope用户")
    user.set_password("pass123")
    db.add(user)
    await db.flush()

    role1 = UserRole(user_id=user.id, role="platform_admin", is_primary=True)
    role2 = UserRole(user_id=user.id, role="homeroom_teacher", school_id=school.id, is_primary=False)
    db.add_all([role1, role2])
    await db.commit()
    await db.refresh(role2)

    # Login → primary role (platform_admin)
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "scope_user", "password": "pass123"},
    )
    token1 = login_resp.json()["access_token"]
    payload1 = decode_token(token1)
    assert payload1["role"] == "platform_admin"

    # Switch to homeroom_teacher (has school_id)
    switch_resp = await client.post(
        "/api/v1/auth/switch-role",
        json={"role_id": role2.id},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert switch_resp.status_code == 200
    token2 = switch_resp.json()["access_token"]
    payload2 = decode_token(token2)
    assert payload2["role"] == "homeroom_teacher"
    assert payload2["active_role_id"] == role2.id

    # New token works for authenticated endpoint
    health_resp = await client.get(
        "/api/v1/schools",
        headers={"Authorization": f"Bearer {token2}"},
    )
    # homeroom_teacher lacks VIEW_SCHOOLS → 403 (proves scope switch worked)
    assert health_resp.status_code == 403


@pytest.mark.asyncio
async def test_login_returns_context(client, seed_teacher):
    """登录响应每个 role 包含 context 对象（type + name）。"""
    resp = await client.post("/api/v1/auth/login", json={"username": "teacher1", "password": "123456"})
    assert resp.status_code == 200
    data = resp.json()
    role = data["roles"][0]
    assert "context" in role
    assert role["context"]["type"] == "school"
    assert role["context"]["name"] == "测试校"


@pytest.mark.asyncio
async def test_login_platform_admin_context(client, admin_user):
    """platform_admin 的 context.type 应为 platform。"""
    resp = await client.post("/api/v1/auth/login", json={"username": "admin_test", "password": "test123"})
    data = resp.json()
    role = data["roles"][0]
    assert role["context"]["type"] == "platform"
    assert role["context"]["name"] == "全平台"


@pytest.mark.asyncio
async def test_switch_role_returns_context(client, db):
    """switch-role 响应也包含 context 对象。"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.models.school import School

    school = School(name="切换测试校", code="SW01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()
    user = User(username="sw_user", display_name="切换用户")
    user.set_password("pass123")
    db.add(user)
    await db.flush()
    role1 = UserRole(user_id=user.id, role="platform_admin", is_primary=True)
    role2 = UserRole(user_id=user.id, role="principal", school_id=school.id, is_primary=False)
    db.add_all([role1, role2])
    await db.commit()
    await db.refresh(role2)

    login = await client.post("/api/v1/auth/login", json={"username": "sw_user", "password": "pass123"})
    token = login.json()["access_token"]
    resp = await client.post("/api/v1/auth/switch-role",
        json={"role_id": role2.id}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["active_role"]["context"]["type"] == "school"
    assert resp.json()["active_role"]["context"]["name"] == "切换测试校"
