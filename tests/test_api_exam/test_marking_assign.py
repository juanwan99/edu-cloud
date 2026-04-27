"""阅卷分配 API 测试。"""
import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def assign_setup(client, db):
    school = School(id="as1", name="分配测试校", code="ASSIGN01")
    db.add(school)
    await db.commit()

    exam = Exam(id="ae1", name="分配考试", card_title="分配", school_id="as1", status="scanning")
    db.add(exam)
    await db.commit()

    subj = Subject(id="asub1", exam_id="ae1", name="语文", code="YW", school_id="as1")
    db.add(subj)
    await db.commit()

    q1 = Question(id="aq1", subject_id="asub1", name="第1题", question_type="essay", max_score=10, school_id="as1")
    q2 = Question(id="aq2", subject_id="asub1", name="第2题", question_type="essay", max_score=10, school_id="as1")
    db.add_all([q1, q2])
    await db.commit()

    admin = User(id="au_admin", username="admin", display_name="管理员")
    admin.set_password("p")
    teacher = User(id="au_teacher", username="teacher", display_name="教师")
    teacher.set_password("p")
    db.add_all([admin, teacher])
    await db.flush()
    db.add_all([
        UserRole(user_id="au_admin", role="admin", school_id="as1", is_primary=True),
        UserRole(user_id="au_teacher", role="teacher", school_id="as1", is_primary=True, subject_codes=["YW"]),
    ])
    await db.commit()

    return {
        "admin": {"Authorization": f"Bearer {create_access_token({'sub': 'au_admin', 'school_id': 'as1', 'role': 'admin'})}"},
        "teacher": {"Authorization": f"Bearer {create_access_token({'sub': 'au_teacher', 'school_id': 'as1', 'role': 'teacher'})}"},
    }


async def test_assign_success(client, assign_setup):
    resp = await client.post("/api/v1/marking/assign", json={
        "exam_id": "ae1", "question_id": "aq1", "teacher_id": "au_teacher",
    }, headers=assign_setup["admin"])
    assert resp.status_code == 201
    assert resp.json()["teacher_id"] == "au_teacher"


async def test_assign_duplicate_409(client, assign_setup):
    await client.post("/api/v1/marking/assign", json={
        "exam_id": "ae1", "question_id": "aq1", "teacher_id": "au_teacher",
    }, headers=assign_setup["admin"])
    resp = await client.post("/api/v1/marking/assign", json={
        "exam_id": "ae1", "question_id": "aq1", "teacher_id": "au_teacher",
    }, headers=assign_setup["admin"])
    assert resp.status_code == 409


async def test_assign_teacher_forbidden(client, assign_setup):
    resp = await client.post("/api/v1/marking/assign", json={
        "exam_id": "ae1", "question_id": "aq1", "teacher_id": "au_teacher",
    }, headers=assign_setup["teacher"])
    assert resp.status_code == 403


async def test_assign_question_wrong_exam(client, assign_setup, db):
    """Question not belonging to the given exam → 400."""
    exam2 = Exam(id="ae2", name="另一考试", card_title="另一", school_id="as1")
    db.add(exam2)
    await db.commit()

    resp = await client.post("/api/v1/marking/assign", json={
        "exam_id": "ae2", "question_id": "aq1", "teacher_id": "au_teacher",
    }, headers=assign_setup["admin"])
    assert resp.status_code == 400


async def test_my_assignments(client, assign_setup):
    # Assign q1 to teacher
    await client.post("/api/v1/marking/assign", json={
        "exam_id": "ae1", "question_id": "aq1", "teacher_id": "au_teacher",
    }, headers=assign_setup["admin"])

    # Teacher sees their assignment
    resp = await client.get("/api/v1/marking/my-assignments", headers=assign_setup["teacher"])
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["question_id"] == "aq1"


async def test_assignments_admin_sees_all(client, assign_setup):
    await client.post("/api/v1/marking/assign", json={
        "exam_id": "ae1", "question_id": "aq1", "teacher_id": "au_teacher",
    }, headers=assign_setup["admin"])
    await client.post("/api/v1/marking/assign", json={
        "exam_id": "ae1", "question_id": "aq2", "teacher_id": "au_teacher",
    }, headers=assign_setup["admin"])

    resp = await client.get("/api/v1/marking/assignments?exam_id=ae1", headers=assign_setup["admin"])
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_assignments_teacher_forbidden(client, assign_setup):
    resp = await client.get("/api/v1/marking/assignments", headers=assign_setup["teacher"])
    assert resp.status_code == 403


async def test_assign_same_question_different_teachers(client, assign_setup, db):
    """同题分配给两个教师 → 都应 201，列表 2 条"""
    teacher2 = User(id="au_teacher2", username="teacher2", display_name="教师B")
    teacher2.set_password("p")
    db.add(teacher2)
    await db.flush()
    db.add(UserRole(user_id="au_teacher2", role="teacher", school_id="as1", is_primary=True, subject_codes=["YW"]))
    await db.commit()

    r1 = await client.post("/api/v1/marking/assign", json={
        "exam_id": "ae1", "question_id": "aq1", "teacher_id": "au_teacher",
    }, headers=assign_setup["admin"])
    assert r1.status_code == 201

    r2 = await client.post("/api/v1/marking/assign", json={
        "exam_id": "ae1", "question_id": "aq1", "teacher_id": "au_teacher2",
    }, headers=assign_setup["admin"])
    assert r2.status_code == 201

    resp = await client.get("/api/v1/marking/assignments?exam_id=ae1", headers=assign_setup["admin"])
    assert len(resp.json()) == 2


async def test_assign_with_answer_count(client, assign_setup):
    """带 answer_count 分配 → 响应包含 answer_count"""
    resp = await client.post("/api/v1/marking/assign", json={
        "exam_id": "ae1", "question_id": "aq1", "teacher_id": "au_teacher",
        "answer_count": 30,
    }, headers=assign_setup["admin"])
    assert resp.status_code == 201

    listing = await client.get("/api/v1/marking/assignments?exam_id=ae1", headers=assign_setup["admin"])
    items = listing.json()
    assert len(items) == 1
    assert items[0]["answer_count"] == 30


async def test_delete_assignment(client, assign_setup):
    """创建→删除→列表为空"""
    resp = await client.post("/api/v1/marking/assign", json={
        "exam_id": "ae1", "question_id": "aq1", "teacher_id": "au_teacher",
    }, headers=assign_setup["admin"])
    assert resp.status_code == 201
    assign_id = resp.json()["id"]

    del_resp = await client.delete(f"/api/v1/marking/assignments/{assign_id}", headers=assign_setup["admin"])
    assert del_resp.status_code == 200

    listing = await client.get("/api/v1/marking/assignments?exam_id=ae1", headers=assign_setup["admin"])
    assert len(listing.json()) == 0


async def test_teachers_list(client, assign_setup):
    resp = await client.get("/api/v1/marking/teachers", headers=assign_setup["admin"])
    assert resp.status_code == 200
    teachers = resp.json()
    assert len(teachers) == 1
    assert teachers[0]["display_name"] == "教师"
    assert teachers[0]["role"] == "teacher"
