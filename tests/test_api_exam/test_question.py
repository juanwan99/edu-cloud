import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def seed_subject(client, db):
    """Create school A + user + exam + subject. Returns (headers, exam_id, subject_id)."""
    school = School(name="School A", code="QA01")
    db.add(school)
    await db.commit()
    user = User(username="teacher_a", display_name="A")
    user.set_password("pass")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="admin", school_id=school.id, is_primary=True))
    await db.flush()
    token = create_access_token({"sub": user.id, "school_id": school.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post("/api/v1/exams", json={"name": "期中", "card_title": "期中考试答题卡"}, headers=headers)
    exam_id = resp.json()["id"]
    resp = await client.post(
        f"/api/v1/exams/{exam_id}/subjects",
        json={"name": "数学", "code": "math"},
        headers=headers,
    )
    subject_id = resp.json()["id"]
    return headers, exam_id, subject_id


@pytest.fixture
async def auth_headers_b(db):
    """Create school B user. Returns headers for school B."""
    school_b = School(name="School B", code="QB01")
    db.add(school_b)
    await db.commit()
    user_b = User(username="teacher_b", display_name="B")
    user_b.set_password("pass")
    db.add(user_b)
    await db.commit()
    db.add(UserRole(user_id=user_b.id, role="admin", school_id=school_b.id, is_primary=True))
    await db.flush()
    token = create_access_token({"sub": user_b.id, "school_id": school_b.id, "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


async def test_create_question(client, seed_subject):
    headers, exam_id, subject_id = seed_subject
    resp = await client.post("/api/v1/questions", json={
        "subject_id": subject_id,
        "name": "第1题",
        "question_type": "essay",
        "max_score": 10.0,
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "第1题"
    assert data["max_score"] == 10.0


async def test_list_questions(client, seed_subject):
    headers, exam_id, subject_id = seed_subject
    await client.post("/api/v1/questions", json={
        "subject_id": subject_id, "name": "Q1",
        "question_type": "choice", "max_score": 5.0,
    }, headers=headers)
    resp = await client.get(f"/api/v1/questions?subject_id={subject_id}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_get_question(client, seed_subject):
    headers, exam_id, subject_id = seed_subject
    create_resp = await client.post("/api/v1/questions", json={
        "subject_id": subject_id, "name": "Q1",
        "question_type": "essay", "max_score": 8.0,
    }, headers=headers)
    qid = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/questions/{qid}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Q1"


async def test_update_question(client, seed_subject):
    headers, exam_id, subject_id = seed_subject
    create_resp = await client.post("/api/v1/questions", json={
        "subject_id": subject_id, "name": "Q1",
        "question_type": "essay", "max_score": 5.0,
    }, headers=headers)
    qid = create_resp.json()["id"]
    resp = await client.patch(f"/api/v1/questions/{qid}", json={"max_score": 15.0}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["max_score"] == 15.0


async def test_delete_question(client, seed_subject):
    headers, exam_id, subject_id = seed_subject
    create_resp = await client.post("/api/v1/questions", json={
        "subject_id": subject_id, "name": "Q-delete",
        "question_type": "choice", "max_score": 3.0,
    }, headers=headers)
    qid = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/questions/{qid}", headers=headers)
    assert resp.status_code == 200
    resp = await client.get(f"/api/v1/questions/{qid}", headers=headers)
    assert resp.status_code == 404


async def test_cross_tenant_question(client, seed_subject, auth_headers_b):
    headers_a, exam_id, subject_id = seed_subject
    # School A creates a question
    await client.post("/api/v1/questions", json={
        "subject_id": subject_id, "name": "Secret Q",
        "question_type": "essay", "max_score": 10.0,
    }, headers=headers_a)
    # School B cannot see it
    resp = await client.get(f"/api/v1/questions?subject_id={subject_id}", headers=auth_headers_b)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_question_invalid_subject(client, seed_subject):
    headers, _, _ = seed_subject
    resp = await client.post("/api/v1/questions", json={
        "subject_id": "nonexistent",
        "name": "Q1",
        "question_type": "essay",
        "max_score": 5.0,
    }, headers=headers)
    assert resp.status_code == 404


async def test_create_question_invalid_type(client, seed_subject):
    """question_type 非法值 → 422。"""
    headers, _, subject_id = seed_subject
    resp = await client.post("/api/v1/questions", json={
        "subject_id": subject_id,
        "name": "Q1",
        "question_type": "invalid_type",
        "max_score": 5.0,
    }, headers=headers)
    assert resp.status_code == 422


async def test_cross_tenant_update_rejected(client, seed_subject, auth_headers_b):
    """学校 B 不能 PATCH 学校 A 的题目 → 404。"""
    headers_a, _, subject_id = seed_subject
    create_resp = await client.post("/api/v1/questions", json={
        "subject_id": subject_id, "name": "Q-cross",
        "question_type": "essay", "max_score": 5.0,
    }, headers=headers_a)
    qid = create_resp.json()["id"]
    resp = await client.patch(f"/api/v1/questions/{qid}", json={"max_score": 99.0}, headers=auth_headers_b)
    assert resp.status_code == 404


async def test_cross_tenant_delete_rejected(client, seed_subject, auth_headers_b):
    """学校 B 不能 DELETE 学校 A 的题目 → 404。"""
    headers_a, _, subject_id = seed_subject
    create_resp = await client.post("/api/v1/questions", json={
        "subject_id": subject_id, "name": "Q-cross-del",
        "question_type": "choice", "max_score": 3.0,
    }, headers=headers_a)
    qid = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/questions/{qid}", headers=auth_headers_b)
    assert resp.status_code == 404


async def test_create_duplicate_question_returns_409(client, seed_subject):
    """F003 T5 回归：POST 同 subject_id + 同 name → 409（非 500）。"""
    headers, _, subject_id = seed_subject
    payload = {
        "subject_id": subject_id, "name": "DupQ",
        "question_type": "choice", "max_score": 5.0,
    }
    resp1 = await client.post("/api/v1/questions", json=payload, headers=headers)
    assert resp1.status_code == 201
    resp2 = await client.post("/api/v1/questions", json=payload, headers=headers)
    assert resp2.status_code == 409, f"Expected 409, got {resp2.status_code}"


async def test_patch_rename_to_existing_name_returns_409(client, seed_subject):
    """F003 T5 回归：PATCH rename 到已存在 name → 409（非 500）。"""
    headers, _, subject_id = seed_subject
    r1 = await client.post("/api/v1/questions", json={
        "subject_id": subject_id, "name": "QA",
        "question_type": "choice", "max_score": 5.0,
    }, headers=headers)
    assert r1.status_code == 201
    r2 = await client.post("/api/v1/questions", json={
        "subject_id": subject_id, "name": "QB",
        "question_type": "choice", "max_score": 5.0,
    }, headers=headers)
    assert r2.status_code == 201
    qb_id = r2.json()["id"]
    resp = await client.patch(f"/api/v1/questions/{qb_id}", json={"name": "QA"}, headers=headers)
    assert resp.status_code == 409, f"Expected 409, got {resp.status_code}"
