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


# ── Middleware tests (Task 4) ──

async def _disable_module(client, admin_headers, school_id, module_code):
    await client.patch(
        f"/api/v1/schools/{school_id}/modules/{module_code}",
        json={"enabled": False},
        headers=admin_headers,
    )


@pytest.mark.asyncio
async def test_middleware_blocks_disabled_module(client, admin_headers, seed_school, db):
    """When calendar module is disabled, /api/v1/calendar/* should return 403."""
    school, _ = seed_school
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.shared.auth import create_access_token

    user = User(username="mw_test_user", display_name="MW Test")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    role = UserRole(user_id=user.id, role="principal", school_id=school.id, is_primary=True)
    db.add(role)
    await db.commit()
    await db.refresh(role)

    token = create_access_token({"sub": user.id, "role": "principal", "active_role_id": role.id})
    headers = {"Authorization": f"Bearer {token}"}

    # Init modules then disable calendar
    await client.get(f"/api/v1/schools/{school.id}/modules", headers=admin_headers)
    await _disable_module(client, admin_headers, school.id, "calendar")

    # calendar API should be blocked
    resp = await client.get("/api/v1/calendar/events", headers=headers)
    assert resp.status_code == 403
    assert "未启用" in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_middleware_allows_enabled_module(client, admin_headers, seed_school, db):
    """When calendar module is enabled (default), /api/v1/calendar/* works normally."""
    school, _ = seed_school
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.shared.auth import create_access_token

    user = User(username="mw_test_user2", display_name="MW Test 2")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    role = UserRole(user_id=user.id, role="principal", school_id=school.id, is_primary=True)
    db.add(role)
    await db.commit()
    await db.refresh(role)

    token = create_access_token({"sub": user.id, "role": "principal", "active_role_id": role.id})
    headers = {"Authorization": f"Bearer {token}"}

    # Init modules — calendar is enabled by default
    await client.get(f"/api/v1/schools/{school.id}/modules", headers=admin_headers)
    resp = await client.get("/api/v1/calendar/events", headers=headers)
    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_middleware_multiple_modules_disabled(client, admin_headers, seed_school, db):
    """Multiple disabled modules are all blocked independently."""
    school, _ = seed_school
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.shared.auth import create_access_token

    user = User(username="mw_multi_test", display_name="MW Multi")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    role = UserRole(user_id=user.id, role="principal", school_id=school.id, is_primary=True)
    db.add(role)
    await db.commit()
    await db.refresh(role)

    token = create_access_token({"sub": user.id, "role": "principal", "active_role_id": role.id})
    headers = {"Authorization": f"Bearer {token}"}

    await client.get(f"/api/v1/schools/{school.id}/modules", headers=admin_headers)
    await _disable_module(client, admin_headers, school.id, "calendar")
    await _disable_module(client, admin_headers, school.id, "studio")

    resp_cal = await client.get("/api/v1/calendar/events", headers=headers)
    resp_studio = await client.get("/api/v1/studio/documents", headers=headers)
    assert resp_cal.status_code == 403
    assert resp_studio.status_code == 403


@pytest.mark.asyncio
async def test_middleware_no_school_id_skips_check(client, admin_headers):
    """Platform admin with no school_id in role -> middleware skips module check."""
    resp = await client.get("/api/v1/calendar/events", headers=admin_headers)
    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_middleware_exempt_paths_always_pass(client):
    """Exempt paths (/api/v1/health, /api/v1/version) are never blocked."""
    resp_health = await client.get("/api/v1/health")
    assert resp_health.status_code == 200
    resp_version = await client.get("/api/v1/version")
    assert resp_version.status_code == 200


@pytest.mark.asyncio
async def test_middleware_multi_school_isolation(client, admin_headers, db):
    """School A disables calendar, School B calendar still works."""
    from edu_cloud.models.school import School
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.shared.auth import create_access_token
    import bcrypt

    hashed = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()
    school_a = School(name="MW School A", code="MW_A", api_key_hash=hashed, district="test")
    school_b = School(name="MW School B", code="MW_B", api_key_hash=hashed, district="test")
    db.add(school_a)
    db.add(school_b)
    await db.flush()

    user_a = User(username="mw_user_a", display_name="User A")
    user_a.set_password("test123")
    user_b = User(username="mw_user_b", display_name="User B")
    user_b.set_password("test123")
    db.add(user_a)
    db.add(user_b)
    await db.flush()

    role_a = UserRole(user_id=user_a.id, role="principal", school_id=school_a.id, is_primary=True)
    role_b = UserRole(user_id=user_b.id, role="principal", school_id=school_b.id, is_primary=True)
    db.add(role_a)
    db.add(role_b)
    await db.commit()
    await db.refresh(role_a)
    await db.refresh(role_b)

    token_a = create_access_token({"sub": user_a.id, "role": "principal", "active_role_id": role_a.id})
    token_b = create_access_token({"sub": user_b.id, "role": "principal", "active_role_id": role_b.id})
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    await client.get(f"/api/v1/schools/{school_a.id}/modules", headers=admin_headers)
    await client.get(f"/api/v1/schools/{school_b.id}/modules", headers=admin_headers)

    # Disable calendar for school A only
    await _disable_module(client, admin_headers, school_a.id, "calendar")

    # School A: blocked
    resp_a = await client.get("/api/v1/calendar/events", headers=headers_a)
    assert resp_a.status_code == 403

    # School B: not blocked
    resp_b = await client.get("/api/v1/calendar/events", headers=headers_b)
    assert resp_b.status_code != 403
