"""Dashboard Summary API 测试 — 角色 scope 精确断言。"""
import pytest


@pytest.mark.asyncio
async def test_dashboard_summary_platform_admin_no_school(client, admin_user, admin_headers):
    """platform_admin 无 school_id → 所有数值字段为 0，deferred 为 null。"""
    resp = await client.get("/api/v1/dashboard/summary", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_students"] == 0
    assert data["total_classes"] == 0
    assert data["total_exams"] == 0
    assert data["total_staff"] is None
    assert data["pending_subjects"] is None
    assert data["pending_grading"] == 0


@pytest.fixture
async def seed_two_classes(db):
    """Seed 两个班级+不同数量学生，用于验证 scope 过滤。
    class_a: 10 学生 | class_b: 5 学生 → 全校 15。"""
    from edu_cloud.models.school import School
    from edu_cloud.models.class_group import ClassGroup
    from edu_cloud.models.student import Student
    from edu_cloud.models.exam import Exam
    school = School(name="Dashboard测试校", code="DASH01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()
    cls_a = ClassGroup(name="七年级1班", grade="七年级", grade_number=7, school_id=school.id)
    cls_b = ClassGroup(name="七年级2班", grade="七年级", grade_number=7, school_id=school.id)
    db.add_all([cls_a, cls_b])
    await db.flush()
    for i in range(10):
        db.add(Student(name=f"A生{i}", student_number=f"A{i:03d}", school_id=school.id, class_id=cls_a.id, grade="七年级"))
    for i in range(5):
        db.add(Student(name=f"B生{i}", student_number=f"B{i:03d}", school_id=school.id, class_id=cls_b.id, grade="七年级"))
    exam = Exam(name="月考", subject_code="SX", subject_name="数学", max_score=100, school_id=school.id, semester="2025-2026-2")
    db.add(exam)
    await db.commit()
    return {"school_id": school.id, "class_a_id": cls_a.id, "class_b_id": cls_b.id}


@pytest.mark.asyncio
async def test_dashboard_summary_principal(client, db, seed_two_classes):
    """校长看到全校聚合：15 学生、2 班级、1 考试。"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    school_id = seed_two_classes["school_id"]
    user = User(username="dash_principal", display_name="仪表盘校长")
    user.set_password("123456")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="principal", school_id=school_id, is_primary=True))
    await db.commit()
    login = await client.post("/api/v1/auth/login", json={"username": "dash_principal", "password": "123456"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.get("/api/v1/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_students"] == 15
    assert data["total_classes"] == 2
    assert data["total_exams"] == 1
    assert data["total_staff"] is None
    assert data["pending_subjects"] is None
    assert "pending_grading" in data


@pytest.mark.asyncio
async def test_dashboard_summary_grade_leader_scoped(client, db, seed_two_classes):
    """年级组长只看 class_a(10 学生)，不看 class_b(5 学生)。"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    school_id = seed_two_classes["school_id"]
    class_a_id = seed_two_classes["class_a_id"]
    user = User(username="dash_leader", display_name="仪表盘组长")
    user.set_password("123456")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="grade_leader", school_id=school_id,
                    class_ids=[class_a_id], is_primary=True))
    await db.commit()
    login = await client.post("/api/v1/auth/login", json={"username": "dash_leader", "password": "123456"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.get("/api/v1/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_students"] == 10
    assert data["total_classes"] == 1


@pytest.mark.asyncio
async def test_dashboard_summary_homeroom_teacher_scoped(client, db, seed_two_classes):
    """班主任只看 class_b(5 学生)。"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    school_id = seed_two_classes["school_id"]
    class_b_id = seed_two_classes["class_b_id"]
    user = User(username="dash_teacher", display_name="仪表盘班主任")
    user.set_password("123456")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="homeroom_teacher", school_id=school_id,
                    class_ids=[class_b_id], is_primary=True))
    await db.commit()
    login = await client.post("/api/v1/auth/login", json={"username": "dash_teacher", "password": "123456"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.get("/api/v1/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_students"] == 5
    assert data["total_classes"] == 1
