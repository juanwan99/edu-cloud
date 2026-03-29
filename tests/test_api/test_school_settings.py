import pytest


@pytest.mark.asyncio
async def test_get_settings(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.get(f"/api/v1/schools/{school.id}/settings", headers=admin_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_upsert_setting(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.patch(
        f"/api/v1/schools/{school.id}/settings",
        json={"category": "feature", "key": "ai_enabled", "value": "true"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["key"] == "ai_enabled"


@pytest.mark.asyncio
async def test_get_modules(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.get(f"/api/v1/schools/{school.id}/modules", headers=admin_headers)
    assert resp.status_code == 200
    modules = resp.json()
    assert len(modules) == 8  # All MODULE_CODES
    codes = {m["code"] for m in modules}
    assert "exam" in codes
    assert "homework" in codes


@pytest.mark.asyncio
async def test_toggle_module(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.patch(
        f"/api/v1/schools/{school.id}/modules/homework",
        json={"enabled": True},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True


@pytest.mark.asyncio
async def test_toggle_invalid_module(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.patch(
        f"/api/v1/schools/{school.id}/modules/nonexistent",
        json={"enabled": True},
        headers=admin_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_settings_requires_auth(client, seed_school):
    school, _ = seed_school
    resp = await client.get(f"/api/v1/schools/{school.id}/settings")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_enabled_modules_endpoint(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.get(f"/api/v1/schools/{school.id}/modules/enabled", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert "exam" in data  # Default enabled


@pytest.mark.asyncio
async def test_principal_can_access_school_settings(client, db):
    """principal has MANAGE_SCHOOL_SETTINGS and can read school settings."""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.models.school import School

    school = School(name="校长配置测试校", code="PRNSET01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()
    user = User(username="principal_settings", display_name="校长配置用户")
    user.set_password("pass123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="principal", school_id=school.id, is_primary=True))
    await db.commit()

    login = await client.post("/api/v1/auth/login", json={"username": "principal_settings", "password": "pass123"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await client.get(f"/api/v1/schools/{school.id}/settings", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_academic_director_can_access_school_modules(client, db):
    """academic_director has MANAGE_SCHOOL_SETTINGS and can read school modules."""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.models.school import School

    school = School(name="教务配置测试校", code="ACDSET01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()
    user = User(username="director_settings", display_name="教务配置用户")
    user.set_password("pass123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="academic_director", school_id=school.id, is_primary=True))
    await db.commit()

    login = await client.post("/api/v1/auth/login", json={"username": "director_settings", "password": "pass123"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await client.get(f"/api/v1/schools/{school.id}/modules", headers=headers)
    assert resp.status_code == 200


# ── Multi-school isolation (F-07 fix) ──

@pytest.mark.asyncio
async def test_modules_multi_school_isolation(client, admin_headers, db):
    """Two schools have independent module states."""
    from edu_cloud.models.school import School
    import bcrypt

    # Create two schools
    for code in ("ISOLATE_A", "ISOLATE_B"):
        hashed = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()
        school = School(name=f"School {code}", code=code, api_key_hash=hashed, district="test")
        db.add(school)
    await db.commit()

    from sqlalchemy import select
    schools = (await db.execute(
        select(School).where(School.code.in_(["ISOLATE_A", "ISOLATE_B"]))
    )).scalars().all()
    school_a, school_b = schools[0], schools[1]

    # Init modules for both
    await client.get(f"/api/v1/schools/{school_a.id}/modules", headers=admin_headers)
    await client.get(f"/api/v1/schools/{school_b.id}/modules", headers=admin_headers)

    # Enable homework for school A, disable for school B
    await client.patch(
        f"/api/v1/schools/{school_a.id}/modules/homework",
        json={"enabled": True}, headers=admin_headers,
    )
    await client.patch(
        f"/api/v1/schools/{school_b.id}/modules/homework",
        json={"enabled": False}, headers=admin_headers,
    )

    # Verify isolation
    resp_a = await client.get(f"/api/v1/schools/{school_a.id}/modules/enabled", headers=admin_headers)
    resp_b = await client.get(f"/api/v1/schools/{school_b.id}/modules/enabled", headers=admin_headers)
    assert "homework" in resp_a.json()
    assert "homework" not in resp_b.json()


# ── Error cases (F-07 fix) ──

@pytest.mark.asyncio
async def test_upsert_setting_missing_key(client, admin_headers, seed_school):
    """PATCH /settings with missing 'key' field should fail."""
    school, _ = seed_school
    resp = await client.patch(
        f"/api/v1/schools/{school.id}/settings",
        json={"category": "feature", "value": "true"},
        headers=admin_headers,
    )
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_toggle_module_missing_enabled(client, admin_headers, seed_school):
    """PATCH /modules/{code} with missing 'enabled' field should fail."""
    school, _ = seed_school
    resp = await client.patch(
        f"/api/v1/schools/{school.id}/modules/exam",
        json={},
        headers=admin_headers,
    )
    assert resp.status_code in (400, 422)
