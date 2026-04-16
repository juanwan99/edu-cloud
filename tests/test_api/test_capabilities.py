import pytest


@pytest.mark.asyncio
async def test_init_capabilities(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.post(
        f"/api/v1/schools/{school.id}/capabilities/init",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_init_capabilities_idempotent(client, admin_headers, seed_school):
    school, _ = seed_school
    await client.post(f"/api/v1/schools/{school.id}/capabilities/init", headers=admin_headers)
    resp = await client.post(f"/api/v1/schools/{school.id}/capabilities/init", headers=admin_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_capabilities(client, admin_headers, seed_school):
    school, _ = seed_school
    await client.post(f"/api/v1/schools/{school.id}/capabilities/init", headers=admin_headers)
    resp = await client.get(f"/api/v1/schools/{school.id}/capabilities", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    assert "role" in data[0]
    assert "domain" in data[0]
    assert "action" in data[0]
    assert "enabled" in data[0]


@pytest.mark.asyncio
async def test_get_capabilities_filter_role(client, admin_headers, seed_school):
    school, _ = seed_school
    await client.post(f"/api/v1/schools/{school.id}/capabilities/init", headers=admin_headers)
    resp = await client.get(
        f"/api/v1/schools/{school.id}/capabilities?role=parent",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2  # study_analytics.read + homework.read
    assert all(d["role"] == "parent" for d in data)
    domains = {d["domain"] for d in data}
    assert "study_analytics" in domains
    assert "homework" in domains


@pytest.mark.asyncio
async def test_patch_capability(client, admin_headers, seed_school):
    school, _ = seed_school
    await client.post(f"/api/v1/schools/{school.id}/capabilities/init", headers=admin_headers)
    resp = await client.patch(
        f"/api/v1/schools/{school.id}/capabilities",
        json={"role": "principal", "domain": "exam", "action": "write", "enabled": False},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False

    # Verify persisted
    resp = await client.get(
        f"/api/v1/schools/{school.id}/capabilities?role=principal",
        headers=admin_headers,
    )
    data = resp.json()
    exam_write = [c for c in data if c["domain"] == "exam" and c["action"] == "write"]
    assert len(exam_write) == 1
    assert exam_write[0]["enabled"] is False


@pytest.mark.asyncio
async def test_patch_capability_invalid_domain(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.patch(
        f"/api/v1/schools/{school.id}/capabilities",
        json={"role": "principal", "domain": "nonexistent", "action": "read", "enabled": True},
        headers=admin_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_capabilities_requires_auth(client, seed_school):
    school, _ = seed_school
    resp = await client.get(f"/api/v1/schools/{school.id}/capabilities")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_capabilities_scope_guard(client, db):
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.models.school import School
    import bcrypt

    hashed = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()
    school_a = School(name="能力A校", code="CAP_A", district="测试区", api_key_hash=hashed)
    school_b = School(name="能力B校", code="CAP_B", district="测试区", api_key_hash=hashed)
    db.add(school_a)
    db.add(school_b)
    await db.flush()
    user = User(username="cap_scope_test", display_name="跨校测试")
    user.set_password("pass123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="principal", school_id=school_a.id, is_primary=True))
    await db.commit()

    login = await client.post("/api/v1/auth/login", json={"username": "cap_scope_test", "password": "pass123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await client.get(f"/api/v1/schools/{school_b.id}/capabilities", headers=headers)
    assert resp.status_code == 403
