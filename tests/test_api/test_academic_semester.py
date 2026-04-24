import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.school import School
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def school(db):
    s = School(name="教务测试校", code="ACAD01", district="测试区")
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


@pytest.fixture
async def director_headers(db, school):
    user = User(username="director_acad", display_name="教务主任")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="academic_director", school_id=school.id, is_primary=True))
    await db.commit()
    token = create_access_token({"sub": user.id, "role": "academic_director", "school_id": school.id})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def teacher_headers(db, school):
    user = User(username="teacher_acad", display_name="科任教师")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="subject_teacher", school_id=school.id, is_primary=True))
    await db.commit()
    token = create_access_token({"sub": user.id, "role": "subject_teacher", "school_id": school.id})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_semester(client, director_headers):
    resp = await client.post("/api/v1/academic/semesters", json={
        "name": "2025-2026学年第一学期", "school_year": "2025-2026",
        "term": 1, "start_date": "2025-09-01", "end_date": "2026-01-15",
    }, headers=director_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "2025-2026学年第一学期"
    assert data["term"] == 1
    assert data["is_current"] is False


@pytest.mark.asyncio
async def test_list_semesters_with_filter(client, director_headers):
    await client.post("/api/v1/academic/semesters", json={
        "name": "S1", "school_year": "2025-2026", "term": 1,
        "start_date": "2025-09-01", "end_date": "2026-01-15",
    }, headers=director_headers)
    await client.post("/api/v1/academic/semesters", json={
        "name": "S2", "school_year": "2025-2026", "term": 2,
        "start_date": "2026-02-17", "end_date": "2026-07-10",
    }, headers=director_headers)
    await client.post("/api/v1/academic/semesters", json={
        "name": "S3", "school_year": "2024-2025", "term": 1,
        "start_date": "2024-09-01", "end_date": "2025-01-15",
    }, headers=director_headers)

    resp = await client.get("/api/v1/academic/semesters", headers=director_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 3

    resp = await client.get("/api/v1/academic/semesters?school_year=2025-2026", headers=director_headers)
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_activate_mutual_exclusion(client, director_headers):
    r1 = await client.post("/api/v1/academic/semesters", json={
        "name": "S1", "school_year": "2025-2026", "term": 1,
        "start_date": "2025-09-01", "end_date": "2026-01-15",
    }, headers=director_headers)
    r2 = await client.post("/api/v1/academic/semesters", json={
        "name": "S2", "school_year": "2025-2026", "term": 2,
        "start_date": "2026-02-17", "end_date": "2026-07-10",
    }, headers=director_headers)
    sid1 = r1.json()["id"]
    sid2 = r2.json()["id"]

    resp = await client.post(f"/api/v1/academic/semesters/{sid1}/activate", headers=director_headers)
    assert resp.status_code == 200
    assert resp.json()["is_current"] is True

    resp = await client.post(f"/api/v1/academic/semesters/{sid2}/activate", headers=director_headers)
    assert resp.status_code == 200
    assert resp.json()["is_current"] is True

    all_sems = await client.get("/api/v1/academic/semesters", headers=director_headers)
    current_count = sum(1 for s in all_sems.json() if s["is_current"])
    assert current_count == 1


@pytest.mark.asyncio
async def test_duplicate_semester_rejected(client, director_headers):
    await client.post("/api/v1/academic/semesters", json={
        "name": "S1", "school_year": "2025-2026", "term": 1,
        "start_date": "2025-09-01", "end_date": "2026-01-15",
    }, headers=director_headers)
    resp = await client.post("/api/v1/academic/semesters", json={
        "name": "S1 duplicate", "school_year": "2025-2026", "term": 1,
        "start_date": "2025-09-01", "end_date": "2026-01-15",
    }, headers=director_headers)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_teacher_cannot_create_semester(client, teacher_headers):
    resp = await client.post("/api/v1/academic/semesters", json={
        "name": "S1", "school_year": "2025-2026", "term": 1,
        "start_date": "2025-09-01", "end_date": "2026-01-15",
    }, headers=teacher_headers)
    assert resp.status_code == 403
