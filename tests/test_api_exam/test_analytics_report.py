"""分析报告 API 测试。"""
import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole


@pytest.fixture
async def report_user(db):
    school = School(name="ReportSchool", code="RPT01")
    db.add(school)
    await db.commit()
    user = User(username="director", display_name="教务主任")
    user.set_password("123456")
    db.add(user)
    await db.commit()
    role = UserRole(user_id=user.id, role="academic_director", school_id=school.id, is_primary=True)
    db.add(role)
    await db.commit()
    return {"user": user, "school": school, "role": role}


async def test_get_segment_config_default(client, report_user, db):
    """未配置时返回硬编码默认值。"""
    from edu_cloud.shared.auth import create_access_token
    token = create_access_token({"sub": report_user["user"].id})
    resp = await client.get(
        "/api/v1/analytics/segments/config",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["default"]["boundaries"] == [85, 70, 60]
    assert data["overrides"] == []


async def test_upsert_segment_config(client, report_user, db):
    from edu_cloud.shared.auth import create_access_token
    token = create_access_token({"sub": report_user["user"].id})
    resp = await client.put(
        "/api/v1/analytics/segments/config",
        json={"boundaries": [90, 75, 60], "labels": ["A", "B", "C", "D"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["boundaries"] == [90, 75, 60]

    # 验证持久化
    resp2 = await client.get(
        "/api/v1/analytics/segments/config",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.json()["default"]["boundaries"] == [90, 75, 60]


from datetime import datetime
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingTask, GradingResult
from edu_cloud.modules.student.models import Class, Student


@pytest.fixture
async def report_exam_data(db, report_user):
    """创建考试数据用于报告测试。"""
    school = report_user["school"]
    user = report_user["user"]
    cls = Class(name="一班", grade="七年级", school_id=school.id)
    db.add(cls)
    await db.commit()

    stu = Student(name="张三", student_number="S001", class_id=cls.id, school_id=school.id)
    db.add(stu)
    await db.commit()

    exam = Exam(name="月考", school_id=school.id, exam_date=datetime(2026, 3, 15))
    db.add(exam)
    await db.commit()
    subj = Subject(exam_id=exam.id, name="数学", code="math", school_id=school.id)
    db.add(subj)
    await db.commit()
    q = Question(subject_id=subj.id, name="Q1", question_type="choice", max_score=100.0, school_id=school.id)
    db.add(q)
    await db.commit()

    task = GradingTask(subject_id=subj.id, school_id=school.id, status="completed", total=1, completed=1, failed=0, created_by=user.id)
    db.add(task)
    await db.commit()

    ans = StudentAnswer(exam_id=exam.id, subject_id=subj.id, student_id=stu.id, question_id=q.id, image_path="/fake.png", school_id=school.id)
    db.add(ans)
    await db.flush()
    gr = GradingResult(answer_id=ans.id, question_id=q.id, ai_score=85.0, final_score=85.0, max_score=100.0, school_id=school.id, ai_task_id=task.id)
    db.add(gr)
    await db.commit()

    return {"exam": exam, "subject": subj, "student": stu, "class": cls}


async def test_report_query(client, report_user, report_exam_data, db):
    from edu_cloud.shared.auth import create_access_token
    token = create_access_token({"sub": report_user["user"].id, "role_id": report_user["role"].id})
    resp = await client.post(
        "/api/v1/analytics/report/query",
        json={
            "exam_ids": [report_exam_data["exam"].id],
            "metrics": ["summary"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "summary" in resp.json()["metrics"]


async def test_grade_trend_api(client, report_user, report_exam_data, db):
    from edu_cloud.shared.auth import create_access_token
    token = create_access_token({"sub": report_user["user"].id, "role_id": report_user["role"].id})
    resp = await client.get(
        "/api/v1/analytics/report/trend/grade",
        params={"exam_ids": report_exam_data["exam"].id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()["points"]) == 1


async def test_export_report(client, report_user, report_exam_data, db):
    from edu_cloud.shared.auth import create_access_token
    token = create_access_token({"sub": report_user["user"].id, "role_id": report_user["role"].id})
    resp = await client.post(
        "/api/v1/analytics/report/export",
        json={
            "exam_ids": [report_exam_data["exam"].id],
            "metrics": ["summary"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert "document_id" in resp.json()


async def test_report_query_restricted_metrics(client, db, report_exam_data, report_user):
    """homeroom_teacher 不能获取 ranking/top_bottom 指标。"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.shared.auth import create_access_token
    import uuid

    school_id = report_user["school"].id
    ht_user = User(id=str(uuid.uuid4()), username="ht_test_r", display_name="班主任", hashed_password="x", is_active=True)
    db.add(ht_user)
    await db.flush()
    ht_role = UserRole(
        user_id=ht_user.id, role="homeroom_teacher", school_id=school_id,
        class_ids=[report_exam_data["class"].id], is_primary=True,
    )
    db.add(ht_role)
    await db.commit()

    token = create_access_token({"sub": ht_user.id, "role_id": ht_role.id})
    resp = await client.post(
        "/api/v1/analytics/report/query",
        json={
            "exam_ids": [report_exam_data["exam"].id],
            "metrics": ["summary", "ranking", "top_bottom"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    metrics = resp.json()["metrics"]
    assert "ranking" not in metrics
    assert "top_bottom" not in metrics
    assert "summary" in metrics


async def test_parent_can_view_own_child_trend(client, db, report_exam_data, report_user):
    """家长通过 guardian 绑定可查看自己孩子的趋势。"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.models.guardian import GuardianStudentLink
    from edu_cloud.shared.auth import create_access_token
    import uuid

    school_id = report_user["school"].id
    parent_user = User(id=str(uuid.uuid4()), username="parent_test", display_name="家长", hashed_password="x", is_active=True)
    db.add(parent_user)
    await db.flush()
    parent_role = UserRole(
        user_id=parent_user.id, role="parent", school_id=school_id,
        is_primary=True,
    )
    db.add(parent_role)
    await db.flush()
    # 创建 guardian 绑定
    link = GuardianStudentLink(
        guardian_user_id=parent_user.id,
        student_id=report_exam_data["student"].id,
        relationship="mother",
        is_primary=True,
        school_id=school_id,
    )
    db.add(link)
    await db.commit()

    token = create_access_token({"sub": parent_user.id, "role_id": parent_role.id})
    resp = await client.get(
        "/api/v1/analytics/report/trend/student",
        params={"exam_ids": report_exam_data["exam"].id, "student_id": report_exam_data["student"].id},
        headers={"Authorization": f"Bearer {token}"},
    )
    # 家长通过 guardian 绑定，不会被 403 拦截
    assert resp.status_code == 200
    data = resp.json()
    assert "points" in data


async def test_parent_forbidden_without_guardian_link(client, db, report_exam_data, report_user):
    """家长无 guardian 绑定时应返回 403。"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.shared.auth import create_access_token
    import uuid

    school_id = report_user["school"].id
    parent_user = User(id=str(uuid.uuid4()), username="parent_no_link", display_name="家长2", hashed_password="x", is_active=True)
    db.add(parent_user)
    await db.flush()
    parent_role = UserRole(
        user_id=parent_user.id, role="parent", school_id=school_id,
        is_primary=True,
    )
    db.add(parent_role)
    await db.commit()

    token = create_access_token({"sub": parent_user.id, "role_id": parent_role.id})
    resp = await client.get(
        "/api/v1/analytics/report/trend/student",
        params={"exam_ids": report_exam_data["exam"].id, "student_id": report_exam_data["student"].id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


async def test_student_trend_forbidden_for_other_class(client, db, report_exam_data, report_user):
    """科任教师请求非任教班学生的 trend/student → 应返回 403。"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.shared.auth import create_access_token
    import uuid

    school_id = report_user["school"].id
    other_cls = Class(name="二班", grade="七年级", school_id=school_id)
    db.add(other_cls)
    await db.commit()
    other_stu = Student(name="李四", student_number="S099", class_id=other_cls.id, school_id=school_id)
    db.add(other_stu)
    await db.commit()

    st_user = User(id=str(uuid.uuid4()), username="st_test_r", display_name="科任", hashed_password="x", is_active=True)
    db.add(st_user)
    await db.flush()
    st_role = UserRole(
        user_id=st_user.id, role="subject_teacher", school_id=school_id,
        class_ids=[report_exam_data["class"].id], is_primary=True,
    )
    db.add(st_role)
    await db.commit()

    token = create_access_token({"sub": st_user.id, "role_id": st_role.id})
    resp = await client.get(
        "/api/v1/analytics/report/trend/student",
        params={"exam_ids": report_exam_data["exam"].id, "student_id": other_stu.id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
