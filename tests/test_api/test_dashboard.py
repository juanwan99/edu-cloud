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
    assert data["total_staff"] == 0
    assert data["pending_subjects"] == 0
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
    assert data["total_staff"] == 1
    assert data["pending_subjects"] == 0
    assert data["pending_grading"] == 0


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
async def test_dashboard_total_staff_counts_non_parent_roles(client, db, seed_two_classes):
    """total_staff 返回本校非 parent 角色的去重用户数。"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    school_id = seed_two_classes["school_id"]
    for i, role in enumerate(["subject_teacher", "homeroom_teacher", "parent"]):
        u = User(username=f"staff_{i}", display_name=f"Staff{i}")
        u.set_password("123456")
        db.add(u)
        await db.flush()
        db.add(UserRole(user_id=u.id, role=role, school_id=school_id, is_primary=True))
    await db.commit()
    login = await client.post("/api/v1/auth/login", json={"username": "staff_0", "password": "123456"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await client.get("/api/v1/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_staff"] == 2


@pytest.mark.asyncio
async def test_dashboard_pending_grading_counts_pending_tasks(client, db, seed_two_classes):
    """pending_grading 返回 status=pending 的 GradingTask 数量。"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.modules.grading.models import GradingTask
    from edu_cloud.modules.exam.models import Exam, Subject
    school_id = seed_two_classes["school_id"]
    u = User(username="grading_user", display_name="阅卷员")
    u.set_password("123456")
    db.add(u)
    await db.flush()
    db.add(UserRole(user_id=u.id, role="academic_director", school_id=school_id, is_primary=True))
    exam = Exam(name="阅卷测试考", subject_code="SX", subject_name="数学", max_score=100, school_id=school_id, semester="2025-2026-2")
    db.add(exam)
    await db.flush()
    subj = Subject(name="数学", code="SX", school_id=school_id, exam_id=exam.id)
    db.add(subj)
    await db.flush()
    db.add(GradingTask(subject_id=subj.id, status="pending", created_by=u.id, school_id=school_id))
    db.add(GradingTask(subject_id=subj.id, status="completed", created_by=u.id, school_id=school_id))
    await db.commit()
    login = await client.post("/api/v1/auth/login", json={"username": "grading_user", "password": "123456"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await client.get("/api/v1/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["pending_grading"] == 1


@pytest.mark.asyncio
async def test_dashboard_pending_subjects_counts_active_grading(client, db, seed_two_classes):
    """pending_subjects 返回有活跃阅卷任务的不同科目数。"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.modules.grading.models import GradingTask
    from edu_cloud.modules.exam.models import Exam, Subject
    school_id = seed_two_classes["school_id"]
    u = User(username="subj_user", display_name="科目员")
    u.set_password("123456")
    db.add(u)
    await db.flush()
    db.add(UserRole(user_id=u.id, role="academic_director", school_id=school_id, is_primary=True))
    exam = Exam(name="科目测试考", subject_code="YW", subject_name="语文", max_score=100, school_id=school_id, semester="2025-2026-2")
    db.add(exam)
    await db.flush()
    s1 = Subject(name="语文", code="YW", school_id=school_id, exam_id=exam.id)
    s2 = Subject(name="英语", code="YY", school_id=school_id, exam_id=exam.id)
    db.add_all([s1, s2])
    await db.flush()
    db.add(GradingTask(subject_id=s1.id, status="pending", created_by=u.id, school_id=school_id))
    db.add(GradingTask(subject_id=s2.id, status="processing", created_by=u.id, school_id=school_id))
    db.add(GradingTask(subject_id=s1.id, status="completed", created_by=u.id, school_id=school_id))
    await db.commit()
    login = await client.post("/api/v1/auth/login", json={"username": "subj_user", "password": "123456"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await client.get("/api/v1/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["pending_subjects"] == 2


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
