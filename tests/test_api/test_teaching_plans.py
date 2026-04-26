"""TDD-lite: TeachingPlan CRUD API tests.

5 test cases:
1. Full CRUD lifecycle (create → list → get → update → delete)
2. UniqueConstraint conflict on duplicate (school+subject+grade+semester)
3. weeks_json format validation
4. Filter by semester/subject_code/grade_id
5. Permission check (subject_teacher cannot create)
"""
import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.school import School
from edu_cloud.models.grade import Grade
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def school(db):
    s = School(name="教学计划测试校", code="TP01", district="测试区")
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


@pytest.fixture
async def grade(db, school):
    g = Grade(name="高一", school_id=school.id)
    db.add(g)
    await db.commit()
    await db.refresh(g)
    return g


@pytest.fixture
async def director_headers(db, school):
    user = User(username="director_tp", display_name="教务主任")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="academic_director", school_id=school.id, is_primary=True))
    await db.commit()
    token = create_access_token({"sub": user.id, "role": "academic_director", "school_id": school.id})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def teacher_headers(db, school):
    user = User(username="teacher_tp", display_name="科任教师")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="subject_teacher", school_id=school.id, is_primary=True))
    await db.commit()
    token = create_access_token({"sub": user.id, "role": "subject_teacher", "school_id": school.id})
    return {"Authorization": f"Bearer {token}"}


VALID_WEEKS = [
    {"week_number": 1, "topic": "函数概念", "knowledge_points": ["定义域", "值域"], "notes": ""},
    {"week_number": 2, "topic": "三角函数", "knowledge_points": ["正弦", "余弦"], "notes": "重点"},
]


@pytest.mark.asyncio
async def test_crud_lifecycle(client, director_headers, grade):
    """Test 1: Full CRUD lifecycle."""
    # CREATE
    resp = await client.post("/api/v1/academic/teaching-plans", json={
        "subject_code": "SX", "grade_id": grade.id,
        "semester": "2025-2026-1", "weeks_json": VALID_WEEKS,
    }, headers=director_headers)
    assert resp.status_code == 201
    plan = resp.json()
    plan_id = plan["id"]
    assert plan["subject_code"] == "SX"
    assert plan["semester"] == "2025-2026-1"
    assert plan["weeks_count"] == 2

    # LIST
    resp = await client.get("/api/v1/academic/teaching-plans", headers=director_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["id"] == plan_id

    # GET
    resp = await client.get(f"/api/v1/academic/teaching-plans/{plan_id}", headers=director_headers)
    assert resp.status_code == 200
    detail = resp.json()
    assert len(detail["weeks_json"]) == 2
    assert detail["weeks_json"][0]["topic"] == "函数概念"

    # UPDATE
    resp = await client.patch(f"/api/v1/academic/teaching-plans/{plan_id}", json={
        "weeks_json": VALID_WEEKS + [{"week_number": 3, "topic": "不等式", "knowledge_points": ["线性"], "notes": ""}],
    }, headers=director_headers)
    assert resp.status_code == 200
    assert resp.json()["weeks_count"] == 3

    # DELETE
    resp = await client.delete(f"/api/v1/academic/teaching-plans/{plan_id}", headers=director_headers)
    assert resp.status_code == 204

    # Verify deleted
    resp = await client.get(f"/api/v1/academic/teaching-plans/{plan_id}", headers=director_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_unique_constraint_conflict(client, director_headers, grade):
    """Test 2: Duplicate (school+subject+grade+semester) rejected with 409."""
    payload = {
        "subject_code": "SX", "grade_id": grade.id,
        "semester": "2025-2026-1", "weeks_json": VALID_WEEKS,
    }
    resp = await client.post("/api/v1/academic/teaching-plans", json=payload, headers=director_headers)
    assert resp.status_code == 201

    resp = await client.post("/api/v1/academic/teaching-plans", json=payload, headers=director_headers)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_weeks_json_validation(client, director_headers, grade):
    """Test 3: weeks_json must be a list of week objects with required fields."""
    # Missing week_number
    bad_weeks = [{"topic": "函数", "knowledge_points": [], "notes": ""}]
    resp = await client.post("/api/v1/academic/teaching-plans", json={
        "subject_code": "SX", "grade_id": grade.id,
        "semester": "2025-2026-1", "weeks_json": bad_weeks,
    }, headers=director_headers)
    assert resp.status_code == 422

    # Not a list
    resp = await client.post("/api/v1/academic/teaching-plans", json={
        "subject_code": "SX", "grade_id": grade.id,
        "semester": "2025-2026-1", "weeks_json": "invalid",
    }, headers=director_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_filter_by_semester_subject_grade(client, director_headers, grade):
    """Test 4: Filter list by semester, subject_code, grade_id."""
    await client.post("/api/v1/academic/teaching-plans", json={
        "subject_code": "SX", "grade_id": grade.id,
        "semester": "2025-2026-1", "weeks_json": VALID_WEEKS,
    }, headers=director_headers)
    await client.post("/api/v1/academic/teaching-plans", json={
        "subject_code": "YW", "grade_id": grade.id,
        "semester": "2025-2026-1", "weeks_json": VALID_WEEKS,
    }, headers=director_headers)
    await client.post("/api/v1/academic/teaching-plans", json={
        "subject_code": "SX", "grade_id": grade.id,
        "semester": "2025-2026-2", "weeks_json": VALID_WEEKS,
    }, headers=director_headers)

    # Filter by semester
    resp = await client.get("/api/v1/academic/teaching-plans?semester=2025-2026-1", headers=director_headers)
    assert len(resp.json()) == 2

    # Filter by subject_code
    resp = await client.get("/api/v1/academic/teaching-plans?subject_code=SX", headers=director_headers)
    assert len(resp.json()) == 2

    # Filter by semester + subject_code
    resp = await client.get("/api/v1/academic/teaching-plans?semester=2025-2026-1&subject_code=SX", headers=director_headers)
    assert len(resp.json()) == 1

    # Filter by grade_id
    resp = await client.get(f"/api/v1/academic/teaching-plans?grade_id={grade.id}", headers=director_headers)
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_teacher_cannot_create(client, teacher_headers, grade):
    """Test 5: subject_teacher lacks MANAGE_SCHEDULING, gets 403."""
    resp = await client.post("/api/v1/academic/teaching-plans", json={
        "subject_code": "SX", "grade_id": grade.id,
        "semester": "2025-2026-1", "weeks_json": VALID_WEEKS,
    }, headers=teacher_headers)
    assert resp.status_code == 403
