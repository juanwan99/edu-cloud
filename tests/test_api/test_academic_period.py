import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.school import School
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def school(db):
    s = School(name="节次测试校", code="PERIOD01", district="测试区")
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


@pytest.fixture
async def director_headers(db, school):
    user = User(username="director_period", display_name="教务主任")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="academic_director", school_id=school.id, is_primary=True))
    await db.commit()
    token = create_access_token({"sub": user.id, "role": "academic_director", "school_id": school.id})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def semester_id(client, director_headers):
    resp = await client.post("/api/v1/academic/semesters", json={
        "name": "S1", "school_year": "2025-2026", "term": 1,
        "start_date": "2025-09-01", "end_date": "2026-01-15",
    }, headers=director_headers)
    return resp.json()["id"]


def _make_periods(n=3):
    times = [("08:00", "08:45"), ("08:55", "09:40"), ("10:00", "10:45")]
    return [
        {"period_number": i + 1, "name": f"第{i+1}节",
         "start_time": times[i][0], "end_time": times[i][1], "period_type": "class"}
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_set_and_get_periods(client, director_headers, semester_id):
    periods = _make_periods(3)
    resp = await client.put("/api/v1/academic/periods", json={
        "semester_id": semester_id, "periods": periods,
    }, headers=director_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 3

    resp = await client.get(f"/api/v1/academic/periods?semester_id={semester_id}", headers=director_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    assert data[0]["period_number"] == 1


@pytest.mark.asyncio
async def test_set_periods_replaces_existing(client, director_headers, semester_id):
    await client.put("/api/v1/academic/periods", json={
        "semester_id": semester_id, "periods": _make_periods(3),
    }, headers=director_headers)

    new_periods = [
        {"period_number": 1, "name": "新第1节", "start_time": "09:00", "end_time": "09:45", "period_type": "class"},
    ]
    resp = await client.put("/api/v1/academic/periods", json={
        "semester_id": semester_id, "periods": new_periods,
    }, headers=director_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = await client.get(f"/api/v1/academic/periods?semester_id={semester_id}", headers=director_headers)
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "新第1节"


@pytest.mark.asyncio
async def test_invalid_period_type_rejected(client, director_headers, semester_id):
    resp = await client.put("/api/v1/academic/periods", json={
        "semester_id": semester_id,
        "periods": [{"period_number": 1, "name": "X", "start_time": "08:00", "end_time": "08:45", "period_type": "invalid"}],
    }, headers=director_headers)
    assert resp.status_code == 422
