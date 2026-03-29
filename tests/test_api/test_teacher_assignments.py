import pytest


@pytest.mark.asyncio
async def test_list_assignments_empty(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.get(f"/api/v1/schools/{school.id}/assignments", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_and_list_assignments(client, admin_headers, seed_school, db):
    school, _ = seed_school
    from edu_cloud.models.user import User
    from edu_cloud.modules.student.models import Class

    user = User(username="api_teacher", display_name="API教师")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    cls = Class(name="高三API班", grade="高三", grade_number=12, school_id=school.id)
    db.add(cls)
    await db.commit()

    resp = await client.post(
        f"/api/v1/schools/{school.id}/assignments",
        json={"user_id": user.id, "class_ids": [cls.id], "subject_code": "math", "semester": "2025-2026-2"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["created"] == 1

    resp = await client.get(f"/api/v1/schools/{school.id}/assignments", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["subject_code"] == "math"


@pytest.mark.asyncio
async def test_delete_assignment(client, admin_headers, seed_school, db):
    school, _ = seed_school
    from edu_cloud.models.user import User
    from edu_cloud.modules.student.models import Class

    user = User(username="api_del_teacher", display_name="删除教师")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    cls = Class(name="删除测试班", grade="高三", grade_number=12, school_id=school.id)
    db.add(cls)
    await db.commit()

    await client.post(
        f"/api/v1/schools/{school.id}/assignments",
        json={"user_id": user.id, "class_ids": [cls.id], "subject_code": "math", "semester": "2025-2026-2"},
        headers=admin_headers,
    )
    rows = (await client.get(f"/api/v1/schools/{school.id}/assignments", headers=admin_headers)).json()
    resp = await client.delete(f"/api/v1/schools/{school.id}/assignments/{rows[0]['id']}", headers=admin_headers)
    assert resp.status_code == 200

    rows = (await client.get(f"/api/v1/schools/{school.id}/assignments", headers=admin_headers)).json()
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_get_summary(client, admin_headers, seed_school, db):
    school, _ = seed_school
    from edu_cloud.models.user import User
    from edu_cloud.modules.student.models import Class

    user = User(username="api_sum_teacher", display_name="摘要教师")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    cls_a = Class(name="摘要1班", grade="高三", grade_number=12, school_id=school.id)
    cls_b = Class(name="摘要2班", grade="高三", grade_number=12, school_id=school.id)
    db.add(cls_a)
    db.add(cls_b)
    await db.commit()

    await client.post(
        f"/api/v1/schools/{school.id}/assignments",
        json={"user_id": user.id, "class_ids": [cls_a.id, cls_b.id], "subject_code": "math", "semester": "2025-2026-2"},
        headers=admin_headers,
    )
    resp = await client.get(f"/api/v1/schools/{school.id}/assignments/summary?semester=2025-2026-2", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["class_count"] == 2


@pytest.mark.asyncio
async def test_assignments_requires_auth(client, seed_school):
    school, _ = seed_school
    resp = await client.get(f"/api/v1/schools/{school.id}/assignments")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_principal_can_manage_own_school_assignments(client, db):
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.models.school import School

    school = School(name="排课权限校", code="ASSGN01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()
    user = User(username="assign_principal", display_name="排课校长")
    user.set_password("pass123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="principal", school_id=school.id, is_primary=True))
    await db.commit()

    login = await client.post("/api/v1/auth/login", json={"username": "assign_principal", "password": "pass123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await client.get(f"/api/v1/schools/{school.id}/assignments", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_principal_cannot_access_other_school_assignments(client, db):
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.models.school import School
    import bcrypt

    hashed = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()
    school_a = School(name="排课A校", code="ASG_A", district="测试区", api_key_hash=hashed)
    school_b = School(name="排课B校", code="ASG_B", district="测试区", api_key_hash=hashed)
    db.add(school_a)
    db.add(school_b)
    await db.flush()
    user = User(username="assign_scope_test", display_name="跨校测试")
    user.set_password("pass123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="principal", school_id=school_a.id, is_primary=True))
    await db.commit()

    login = await client.post("/api/v1/auth/login", json={"username": "assign_scope_test", "password": "pass123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await client.get(f"/api/v1/schools/{school_b.id}/assignments", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_assignments_empty_class_ids_rejected(client, admin_headers, seed_school):
    """P6 fix: empty class_ids should be rejected by Pydantic validation."""
    school, _ = seed_school
    resp = await client.post(
        f"/api/v1/schools/{school.id}/assignments",
        json={"user_id": "any", "class_ids": [], "subject_code": "math", "semester": "2025-2026-2"},
        headers=admin_headers,
    )
    assert resp.status_code == 422
