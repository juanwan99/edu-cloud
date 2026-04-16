import pytest


@pytest.mark.asyncio
async def test_list_selections_empty(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.get(f"/api/v1/schools/{school.id}/selections", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_selection(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.post(
        f"/api/v1/schools/{school.id}/selections",
        json={"name": "物化生", "subject_codes": ["physics", "chemistry", "biology"], "mode": "3+1+2"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "物化生"
    assert data["subject_codes"] == ["physics", "chemistry", "biology"]
    assert data["mode"] == "3+1+2"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_create_selection_invalid_mode(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.post(
        f"/api/v1/schools/{school.id}/selections",
        json={"name": "无效", "subject_codes": ["physics"], "mode": "invalid"},
        headers=admin_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_selection_empty_subjects(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.post(
        f"/api/v1/schools/{school.id}/selections",
        json={"name": "空", "subject_codes": []},
        headers=admin_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_selection_duplicate_name(client, admin_headers, seed_school):
    """P1 fix: duplicate name → 409 ConflictError."""
    school, _ = seed_school
    await client.post(
        f"/api/v1/schools/{school.id}/selections",
        json={"name": "重复API", "subject_codes": ["physics"]},
        headers=admin_headers,
    )
    resp = await client.post(
        f"/api/v1/schools/{school.id}/selections",
        json={"name": "重复API", "subject_codes": ["chemistry"]},
        headers=admin_headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_update_selection(client, admin_headers, seed_school):
    school, _ = seed_school
    create_resp = await client.post(
        f"/api/v1/schools/{school.id}/selections",
        json={"name": "更新测试", "subject_codes": ["physics"]},
        headers=admin_headers,
    )
    sel_id = create_resp.json()["id"]
    resp = await client.patch(
        f"/api/v1/schools/{school.id}/selections/{sel_id}",
        json={"name": "更新后", "is_active": False},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "更新后"
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_delete_selection(client, admin_headers, seed_school):
    school, _ = seed_school
    create_resp = await client.post(
        f"/api/v1/schools/{school.id}/selections",
        json={"name": "删除测试", "subject_codes": ["physics"]},
        headers=admin_headers,
    )
    sel_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/schools/{school.id}/selections/{sel_id}", headers=admin_headers)
    assert resp.status_code == 200

    rows = (await client.get(f"/api/v1/schools/{school.id}/selections", headers=admin_headers)).json()
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_selections_requires_auth(client, seed_school):
    school, _ = seed_school
    resp = await client.get(f"/api/v1/schools/{school.id}/selections")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_principal_cannot_access_other_school_selections(client, db):
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.models.school import School
    import bcrypt

    hashed = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()
    school_a = School(name="选考A校", code="SEL_A", district="测试区", api_key_hash=hashed)
    school_b = School(name="选考B校", code="SEL_B", district="测试区", api_key_hash=hashed)
    db.add(school_a)
    db.add(school_b)
    await db.flush()
    user = User(username="sel_scope_test", display_name="选考跨校")
    user.set_password("pass123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="principal", school_id=school_a.id, is_primary=True))
    await db.commit()

    login = await client.post("/api/v1/auth/login", json={"username": "sel_scope_test", "password": "pass123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await client.get(f"/api/v1/schools/{school_b.id}/selections", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_selection_duplicate_name_409(client, admin_headers, seed_school):
    """F01 fix: PATCH to existing name → 409."""
    school, _ = seed_school
    await client.post(
        f"/api/v1/schools/{school.id}/selections",
        json={"name": "已有API", "subject_codes": ["physics"]},
        headers=admin_headers,
    )
    create_resp = await client.post(
        f"/api/v1/schools/{school.id}/selections",
        json={"name": "待改API", "subject_codes": ["history"]},
        headers=admin_headers,
    )
    sel_id = create_resp.json()["id"]
    resp = await client.patch(
        f"/api/v1/schools/{school.id}/selections/{sel_id}",
        json={"name": "已有API"},
        headers=admin_headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_selection_empty_string_subject_422(client, admin_headers, seed_school):
    """F02 fix: empty string in subject_codes → 422."""
    school, _ = seed_school
    resp = await client.post(
        f"/api/v1/schools/{school.id}/selections",
        json={"name": "空元素API", "subject_codes": ["physics", ""]},
        headers=admin_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_selection_empty_string_subject_422(client, admin_headers, seed_school):
    """F02 fix: PATCH with empty string in subject_codes → 422."""
    school, _ = seed_school
    create_resp = await client.post(
        f"/api/v1/schools/{school.id}/selections",
        json={"name": "PATCH空元素", "subject_codes": ["physics"]},
        headers=admin_headers,
    )
    sel_id = create_resp.json()["id"]
    resp = await client.patch(
        f"/api/v1/schools/{school.id}/selections/{sel_id}",
        json={"subject_codes": ["chemistry", ""]},
        headers=admin_headers,
    )
    assert resp.status_code == 422
