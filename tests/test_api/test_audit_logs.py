import pytest


@pytest.mark.asyncio
async def test_list_audit_logs_empty(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.get(f"/api/v1/schools/{school.id}/audit-logs", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_audit_logs_after_setting_change(client, admin_headers, seed_school):
    school, _ = seed_school
    await client.patch(
        f"/api/v1/schools/{school.id}/settings",
        json={"key": "api_audit_test", "value": "hello"},
        headers=admin_headers,
    )
    resp = await client.get(f"/api/v1/schools/{school.id}/audit-logs", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["entity_type"] == "school_setting"


@pytest.mark.asyncio
async def test_audit_log_captures_user_and_request_id(client, admin_headers, seed_school):
    """F-06: API-level test verifying JWT sub and request_id flow into audit logs."""
    school, _ = seed_school
    custom_headers = {**admin_headers, "X-Request-ID": "f06-test-req-id"}
    await client.patch(
        f"/api/v1/schools/{school.id}/settings",
        json={"key": "f06_test_key", "value": "v1"},
        headers=custom_headers,
    )
    resp = await client.get(f"/api/v1/schools/{school.id}/audit-logs", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    # F-06: user_id should be the admin user's ID (not None, not "-")
    assert data[0]["user_id"] is not None
    assert data[0]["user_id"] != "-"
    # F-06: request_id should be the custom header we sent
    assert data[0]["request_id"] == "f06-test-req-id"


@pytest.mark.asyncio
async def test_list_audit_logs_filter_entity_type(client, admin_headers, seed_school, db):
    school, _ = seed_school
    await client.patch(
        f"/api/v1/schools/{school.id}/settings",
        json={"key": "filter_test_key", "value": "v1"},
        headers=admin_headers,
    )
    await client.post(
        f"/api/v1/schools/{school.id}/selections",
        json={"name": "审计过滤理化生", "subject_codes": ["physics", "chemistry", "biology"], "mode": "custom"},
        headers=admin_headers,
    )

    resp = await client.get(
        f"/api/v1/schools/{school.id}/audit-logs?entity_type=school_setting",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(d["entity_type"] == "school_setting" for d in data)


@pytest.mark.asyncio
async def test_list_audit_logs_pagination(client, admin_headers, seed_school):
    school, _ = seed_school
    for i in range(5):
        await client.patch(
            f"/api/v1/schools/{school.id}/settings",
            json={"key": f"page_test_{i}", "value": f"v{i}"},
            headers=admin_headers,
        )

    resp = await client.get(
        f"/api/v1/schools/{school.id}/audit-logs?limit=2&offset=0",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    resp = await client.get(
        f"/api/v1/schools/{school.id}/audit-logs?limit=2&offset=3",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_audit_logs_requires_auth(client, seed_school):
    school, _ = seed_school
    resp = await client.get(f"/api/v1/schools/{school.id}/audit-logs")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_audit_logs_scope_guard(client, db):
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.models.school import School
    import bcrypt

    hashed = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()
    school_a = School(name="审计A校", code="AUD_A", district="测试区", api_key_hash=hashed)
    school_b = School(name="审计B校", code="AUD_B", district="测试区", api_key_hash=hashed)
    db.add(school_a)
    db.add(school_b)
    await db.flush()
    user = User(username="audit_scope_test", display_name="跨校审计测试")
    user.set_password("pass123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="principal", school_id=school_a.id, is_primary=True))
    await db.commit()

    login = await client.post("/api/v1/auth/login", json={"username": "audit_scope_test", "password": "pass123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await client.get(f"/api/v1/schools/{school_b.id}/audit-logs", headers=headers)
    assert resp.status_code == 403
