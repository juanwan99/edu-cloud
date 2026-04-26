import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.school import School
from edu_cloud.modules.student.models import Class
from edu_cloud.modules.academic.models import Semester, TimePeriod
from edu_cloud.shared.auth import create_access_token
from datetime import date, time as time_type


@pytest.fixture
async def setup(db):
    school = School(name="课表测试校", code="TT01", district="测试区")
    db.add(school)
    await db.flush()

    sem = Semester(school_id=school.id, name="S1", school_year="2025-2026", term=1,
                   start_date=date(2025, 9, 1), end_date=date(2026, 1, 15), is_current=True)
    db.add(sem)
    await db.flush()

    tp = TimePeriod(school_id=school.id, semester_id=sem.id, period_number=1,
                    name="第一节", start_time=time_type(8, 0), end_time=time_type(8, 45), period_type="class")
    db.add(tp)
    await db.flush()

    cls1 = Class(name="初一1班", grade="初一", school_id=school.id)
    cls2 = Class(name="初一2班", grade="初一", school_id=school.id)
    db.add_all([cls1, cls2])
    await db.flush()

    teacher = User(username="math_teacher_tt", display_name="数学老师")
    teacher.set_password("test123")
    db.add(teacher)
    await db.flush()
    db.add(UserRole(user_id=teacher.id, role="subject_teacher", school_id=school.id, is_primary=True))

    director = User(username="director_tt", display_name="教务主任")
    director.set_password("test123")
    db.add(director)
    await db.flush()
    db.add(UserRole(user_id=director.id, role="academic_director", school_id=school.id, is_primary=True))

    await db.commit()
    for obj in [school, sem, tp, cls1, cls2, teacher, director]:
        await db.refresh(obj)

    d_token = create_access_token({"sub": director.id, "role": "academic_director", "school_id": school.id})
    t_token = create_access_token({"sub": teacher.id, "role": "subject_teacher", "school_id": school.id})

    return {
        "school": school, "semester": sem, "period": tp,
        "class1": cls1, "class2": cls2, "teacher": teacher,
        "director_headers": {"Authorization": f"Bearer {d_token}"},
        "teacher_headers": {"Authorization": f"Bearer {t_token}"},
    }


@pytest.mark.asyncio
async def test_save_and_get_timetable(client, setup):
    s = setup
    slot = {"weekday": 1, "period_id": s["period"].id, "subject_code": "math", "teacher_id": s["teacher"].id}
    resp = await client.put(f"/api/v1/academic/timetable/{s['class1'].id}", json={
        "semester_id": s["semester"].id, "slots": [slot],
    }, headers=s["director_headers"])
    assert resp.status_code == 200
    assert resp.json()["saved"] == 1

    resp = await client.get(f"/api/v1/academic/timetable?semester_id={s['semester'].id}&class_id={s['class1'].id}",
                            headers=s["director_headers"])
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["subject_code"] == "math"


@pytest.mark.asyncio
async def test_teacher_conflict_rejected(client, setup):
    s = setup
    slot = {"weekday": 1, "period_id": s["period"].id, "subject_code": "math", "teacher_id": s["teacher"].id}
    await client.put(f"/api/v1/academic/timetable/{s['class1'].id}", json={
        "semester_id": s["semester"].id, "slots": [slot],
    }, headers=s["director_headers"])

    resp = await client.put(f"/api/v1/academic/timetable/{s['class2'].id}", json={
        "semester_id": s["semester"].id, "slots": [slot],
    }, headers=s["director_headers"])
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_query_by_teacher(client, setup):
    s = setup
    slot = {"weekday": 1, "period_id": s["period"].id, "subject_code": "math", "teacher_id": s["teacher"].id}
    await client.put(f"/api/v1/academic/timetable/{s['class1'].id}", json={
        "semester_id": s["semester"].id, "slots": [slot],
    }, headers=s["director_headers"])

    resp = await client.get(
        f"/api/v1/academic/timetable?semester_id={s['semester'].id}&teacher_id={s['teacher'].id}",
        headers=s["director_headers"])
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_timetable_stats(client, setup):
    s = setup
    slots = [
        {"weekday": 1, "period_id": s["period"].id, "subject_code": "math", "teacher_id": s["teacher"].id},
    ]
    await client.put(f"/api/v1/academic/timetable/{s['class1'].id}", json={
        "semester_id": s["semester"].id, "slots": slots,
    }, headers=s["director_headers"])

    resp = await client.get(
        f"/api/v1/academic/timetable/stats?semester_id={s['semester'].id}&class_id={s['class1'].id}",
        headers=s["director_headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert any(d["subject_code"] == "math" and d["count"] == 1 for d in data)


@pytest.mark.asyncio
async def test_timetable_stats_school_wide(client, setup):
    """When class_id is omitted, stats returns school-wide summary."""
    s = setup
    # Save a timetable for class1 only
    slot = {"weekday": 1, "period_id": s["period"].id, "subject_code": "math", "teacher_id": s["teacher"].id}
    await client.put(f"/api/v1/academic/timetable/{s['class1'].id}", json={
        "semester_id": s["semester"].id, "slots": [slot],
    }, headers=s["director_headers"])

    # Call stats without class_id
    resp = await client.get(
        f"/api/v1/academic/timetable/stats?semester_id={s['semester'].id}",
        headers=s["director_headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_classes"] == 2  # class1 + class2
    assert data["classes_with_timetable"] == 1  # only class1
    assert 0 < data["coverage_rate"] < 1


@pytest.mark.asyncio
async def test_teacher_cannot_save_timetable(client, setup):
    s = setup
    slot = {"weekday": 1, "period_id": s["period"].id, "subject_code": "math", "teacher_id": s["teacher"].id}
    resp = await client.put(f"/api/v1/academic/timetable/{s['class1'].id}", json={
        "semester_id": s["semester"].id, "slots": [slot],
    }, headers=s["teacher_headers"])
    assert resp.status_code == 403
