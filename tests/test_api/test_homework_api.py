"""作业 API 端点测试。"""
import pytest


@pytest.fixture
async def hw_api_fixtures(db):
    """创建 school + teacher(homeroom) + class + students 用于 API 测试。"""
    from edu_cloud.models.school import School
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.models.class_group import ClassGroup
    from edu_cloud.models.student import Student

    school = School(name="API测试校", code="HWAPI", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    teacher = User(username="hw_api_teacher", display_name="API老师")
    teacher.set_password("123456")
    db.add(teacher)
    await db.flush()

    db.add(UserRole(
        user_id=teacher.id, role="homeroom_teacher",
        school_id=school.id, class_ids=[], is_primary=True,
    ))

    cls = ClassGroup(name="八年级1班", grade="八年级", grade_number=8, school_id=school.id)
    db.add(cls)
    await db.flush()

    students = []
    for i in range(3):
        s = Student(
            name=f"API学生{i}", student_number=f"API{i:03d}",
            school_id=school.id, grade="八年级", class_id=cls.id,
        )
        db.add(s)
        students.append(s)
    await db.flush()
    await db.commit()

    return {
        "school_id": school.id, "teacher_id": teacher.id,
        "class_id": cls.id, "student_ids": [s.id for s in students],
    }


@pytest.fixture
async def hw_teacher_headers(client, hw_api_fixtures):
    """homeroom_teacher JWT headers。"""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "hw_api_teacher", "password": "123456"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_task(client, hw_teacher_headers, hw_api_fixtures):
    resp = await client.post(
        "/api/v1/homework/tasks",
        json={
            "title": "API测试作业",
            "task_type": "regular",
            "subject_code": "SX",
            "class_id": hw_api_fixtures["class_id"],
        },
        headers=hw_teacher_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "API测试作业"
    assert data["status"] == "draft"


@pytest.mark.asyncio
async def test_list_tasks(client, hw_teacher_headers, hw_api_fixtures):
    # 先创建一条
    await client.post(
        "/api/v1/homework/tasks",
        json={"title": "列表测试", "task_type": "regular", "subject_code": "SX"},
        headers=hw_teacher_headers,
    )
    resp = await client.get("/api/v1/homework/tasks", headers=hw_teacher_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_publish_and_submissions(client, hw_teacher_headers, hw_api_fixtures):
    # 创建
    create_resp = await client.post(
        "/api/v1/homework/tasks",
        json={
            "title": "发布API测试", "task_type": "regular",
            "subject_code": "SX", "class_id": hw_api_fixtures["class_id"],
        },
        headers=hw_teacher_headers,
    )
    task_id = create_resp.json()["id"]

    # 发布
    pub_resp = await client.post(
        f"/api/v1/homework/tasks/{task_id}/publish",
        headers=hw_teacher_headers,
    )
    assert pub_resp.status_code == 200
    assert pub_resp.json()["status"] == "active"

    # 查看提交
    subs_resp = await client.get(
        f"/api/v1/homework/tasks/{task_id}/submissions",
        headers=hw_teacher_headers,
    )
    assert subs_resp.status_code == 200
    assert len(subs_resp.json()) == 3


@pytest.mark.asyncio
async def test_grade_batch_api(client, hw_teacher_headers, hw_api_fixtures):
    # 创建+发布
    create_resp = await client.post(
        "/api/v1/homework/tasks",
        json={
            "title": "批改API测试", "task_type": "regular",
            "subject_code": "SX", "class_id": hw_api_fixtures["class_id"],
        },
        headers=hw_teacher_headers,
    )
    task_id = create_resp.json()["id"]
    await client.post(f"/api/v1/homework/tasks/{task_id}/publish", headers=hw_teacher_headers)

    # 先提交
    subs_resp = await client.get(f"/api/v1/homework/tasks/{task_id}/submissions", headers=hw_teacher_headers)
    for sub in subs_resp.json():
        await client.post(
            f"/api/v1/homework/tasks/{task_id}/submissions/{sub['id']}/submit",
            json={"content": "{}"},
            headers=hw_teacher_headers,
        )

    # 批量批改
    grades = [
        {"student_id": hw_api_fixtures["student_ids"][0], "score": 90, "feedback": "好"},
        {"student_id": hw_api_fixtures["student_ids"][1], "score": 75},
    ]
    grade_resp = await client.post(
        f"/api/v1/homework/tasks/{task_id}/grade-batch",
        json={"grades": grades},
        headers=hw_teacher_headers,
    )
    assert grade_resp.status_code == 200
    assert grade_resp.json()["graded_count"] == 2


@pytest.mark.asyncio
async def test_stats_api(client, hw_teacher_headers, hw_api_fixtures):
    create_resp = await client.post(
        "/api/v1/homework/tasks",
        json={
            "title": "统计API测试", "task_type": "regular",
            "subject_code": "SX", "class_id": hw_api_fixtures["class_id"],
        },
        headers=hw_teacher_headers,
    )
    task_id = create_resp.json()["id"]
    await client.post(f"/api/v1/homework/tasks/{task_id}/publish", headers=hw_teacher_headers)

    stats_resp = await client.get(
        f"/api/v1/homework/tasks/{task_id}/stats",
        headers=hw_teacher_headers,
    )
    assert stats_resp.status_code == 200
    data = stats_resp.json()
    assert data["total"] == 3
    assert data["pending"] == 3


@pytest.mark.asyncio
async def test_permission_denied(client, observer_headers):
    """observer 无作业权限。"""
    resp = await client.post(
        "/api/v1/homework/tasks",
        json={"title": "无权限", "task_type": "regular", "subject_code": "SX"},
        headers=observer_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_draft(client, hw_teacher_headers):
    create_resp = await client.post(
        "/api/v1/homework/tasks",
        json={"title": "待删除", "task_type": "regular", "subject_code": "SX"},
        headers=hw_teacher_headers,
    )
    task_id = create_resp.json()["id"]
    del_resp = await client.delete(f"/api/v1/homework/tasks/{task_id}", headers=hw_teacher_headers)
    assert del_resp.status_code == 204
