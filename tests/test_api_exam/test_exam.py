import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def auth(db):
    school = School(name="Test School", code="EX01")
    db.add(school)
    await db.commit()
    user = User(username="teacher", display_name="Teacher")
    user.set_password("pass")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="admin", school_id=school.id, is_primary=True))
    await db.flush()
    token = create_access_token({"sub": user.id, "school_id": school.id, "role": "admin"})
    return token, school.id


async def test_create_exam(client, auth):
    token, school_id = auth
    resp = await client.post("/api/v1/exams", json={"name": "期中考试", "card_title": "期中考试答题卡"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "期中考试"
    assert data["school_id"] == school_id
    assert data["status"] == "draft"


async def test_list_exams(client, auth):
    token, school_id = auth
    # create one first
    await client.post("/api/v1/exams", json={"name": "期末考试", "card_title": "期末考试答题卡"}, headers={"Authorization": f"Bearer {token}"})
    resp = await client.get("/api/v1/exams", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_get_exam(client, auth):
    token, _ = auth
    create_resp = await client.post("/api/v1/exams", json={"name": "月考", "card_title": "月考答题卡"}, headers={"Authorization": f"Bearer {token}"})
    exam_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/exams/{exam_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "月考"


async def test_get_exam_not_found(client, auth):
    token, _ = auth
    resp = await client.get("/api/v1/exams/nonexistent", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


async def test_cross_tenant_isolation(client, auth, db):
    token_a, _ = auth
    school_b = School(name="School B", code="EX02")
    db.add(school_b)
    await db.commit()
    user_b = User(username="tb", display_name="B")
    user_b.set_password("pass")
    db.add(user_b)
    await db.commit()
    db.add(UserRole(user_id=user_b.id, role="admin", school_id=school_b.id, is_primary=True))
    await db.flush()
    token_b = create_access_token({"sub": user_b.id, "school_id": school_b.id, "role": "admin"})

    # school A creates exam
    resp = await client.post("/api/v1/exams", json={"name": "隔离测试", "card_title": "隔离测试答题卡"}, headers={"Authorization": f"Bearer {token_a}"})
    exam_id = resp.json()["id"]

    # school B cannot see it
    resp = await client.get(f"/api/v1/exams/{exam_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 404
    resp = await client.get("/api/v1/exams", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.json() == []


async def test_list_exams_empty(client, auth):
    token, _ = auth
    resp = await client.get("/api/v1/exams", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_exam_missing_name(client, auth):
    token, _ = auth
    resp = await client.post("/api/v1/exams", json={}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 422


# --- Status transition tests (TG-001) ---


async def test_update_exam_status_draft_to_scanning(client, auth):
    """draft → scanning should succeed."""
    token, _ = auth
    resp = await client.post("/api/v1/exams", json={"name": "状态测试", "card_title": "答题卡"}, headers={"Authorization": f"Bearer {token}"})
    exam_id = resp.json()["id"]
    assert resp.json()["status"] == "draft"

    resp = await client.patch(f"/api/v1/exams/{exam_id}", json={"status": "scanning"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "scanning"


async def test_update_exam_status_invalid_transition(client, auth):
    """draft → grading should fail (invalid transition)."""
    token, _ = auth
    resp = await client.post("/api/v1/exams", json={"name": "非法状态", "card_title": "答题卡"}, headers={"Authorization": f"Bearer {token}"})
    exam_id = resp.json()["id"]

    resp = await client.patch(f"/api/v1/exams/{exam_id}", json={"status": "grading"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 422  # edu-cloud: ValidationError → 422


async def test_update_exam_status_duplicate_scanning(client, auth):
    """scanning → scanning should fail (not in allowed transitions)."""
    token, _ = auth
    resp = await client.post("/api/v1/exams", json={"name": "重复发布", "card_title": "答题卡"}, headers={"Authorization": f"Bearer {token}"})
    exam_id = resp.json()["id"]

    # draft → scanning
    resp = await client.patch(f"/api/v1/exams/{exam_id}", json={"status": "scanning"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    # scanning → scanning should fail
    resp = await client.patch(f"/api/v1/exams/{exam_id}", json={"status": "scanning"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 422  # edu-cloud: ValidationError → 422


async def test_update_exam_status_scanning_back_to_draft(client, auth):
    """scanning → draft should succeed (rollback)."""
    token, _ = auth
    resp = await client.post("/api/v1/exams", json={"name": "回退测试", "card_title": "答题卡"}, headers={"Authorization": f"Bearer {token}"})
    exam_id = resp.json()["id"]

    await client.patch(f"/api/v1/exams/{exam_id}", json={"status": "scanning"}, headers={"Authorization": f"Bearer {token}"})
    resp = await client.patch(f"/api/v1/exams/{exam_id}", json={"status": "draft"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "draft"
