"""考后推送补救作业 API 测试 (WP-C TDD-lite)。

覆盖:
  1. POST /homework/tasks/from-exam — 考后推送创建成功
  2. POST /homework/tasks/from-exam — 无错题时行为（空考试）
  3. GET /homework/tasks/{id}/content-detail — content-detail 解析
  4. 权限校验 — observer 无权创建
"""
import json
import pytest

from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.class_group import ClassGroup
from edu_cloud.models.student import Student
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.bank.models import BankQuestion


@pytest.fixture
async def remedial_fixtures(db):
    """创建完整的考后推送测试数据：学校+教师+班级+学生+考试+题目+作答+题库。"""
    school = School(name="补救测试校", code="REMEDIAL01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    teacher = User(username="remedial_teacher", display_name="补救老师")
    teacher.set_password("123456")
    db.add(teacher)
    await db.flush()
    db.add(UserRole(
        user_id=teacher.id, role="homeroom_teacher",
        school_id=school.id, class_ids=[], is_primary=True,
    ))

    cls = ClassGroup(name="九年级1班", grade="九年级", grade_number=9, school_id=school.id)
    db.add(cls)
    await db.flush()

    students = []
    for i in range(5):
        s = Student(
            name=f"补救学生{i}", student_number=f"REM{i:03d}",
            school_id=school.id, grade="九年级", class_id=cls.id,
        )
        db.add(s)
        students.append(s)
    await db.flush()

    # 考试 + 科目 + 题目
    exam = Exam(
        name="期中数学考试", subject_code="SX", subject_name="数学",
        max_score=100, school_id=school.id, semester="2025-2026-2",
    )
    db.add(exam)
    await db.flush()

    subject = Subject(
        name="数学", code="SX", exam_id=exam.id,
        school_id=school.id,
    )
    db.add(subject)
    await db.flush()

    # 3 道题
    questions = []
    for name, max_s, q_type in [
        ("选择题1", 5.0, "choice"),
        ("填空题1", 10.0, "fill"),
        ("解答题1", 15.0, "essay"),
    ]:
        q = Question(
            name=name, question_type=q_type, max_score=max_s,
            subject_id=subject.id, school_id=school.id,
        )
        db.add(q)
        questions.append(q)
    await db.flush()

    # 学生作答 — 第 2 和第 3 题大量错误（错误率 > 40%）
    for s in students:
        # 题1: 大部分对 (4/5 得分)
        db.add(StudentAnswer(
            student_id=s.id, question_id=questions[0].id,
            subject_id=subject.id, school_id=school.id,
            exam_id=exam.id, score=4.0,
        ))
        # 题2: 大部分错 (2/10 得分 → 80% 错误率)
        db.add(StudentAnswer(
            student_id=s.id, question_id=questions[1].id,
            subject_id=subject.id, school_id=school.id,
            exam_id=exam.id, score=2.0,
        ))
        # 题3: 大部分错 (3/15 得分 → 80% 错误率)
        db.add(StudentAnswer(
            student_id=s.id, question_id=questions[2].id,
            subject_id=subject.id, school_id=school.id,
            exam_id=exam.id, score=3.0,
        ))
    await db.flush()

    # 题库中有同知识点/同题型的练习题
    bank_questions = []
    for i in range(4):
        bq = BankQuestion(
            content_text=f"练习题{i+1}内容",
            question_type="fill" if i < 2 else "essay",
            max_score=10.0,
            school_id=school.id,
            knowledge_point_ids=["kp_001", "kp_002"],
            source="manual",
        )
        db.add(bq)
        bank_questions.append(bq)
    await db.flush()
    await db.commit()

    return {
        "school_id": school.id,
        "teacher_id": teacher.id,
        "class_id": cls.id,
        "exam_id": exam.id,
        "subject_id": subject.id,
        "question_ids": [q.id for q in questions],
        "student_ids": [s.id for s in students],
        "bank_question_ids": [bq.id for bq in bank_questions],
    }


@pytest.fixture
async def remedial_headers(client, remedial_fixtures):
    """homeroom_teacher JWT headers for remedial tests."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "remedial_teacher", "password": "123456"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── Test 1: 考后推送创建成功 ──

@pytest.mark.asyncio
async def test_create_remedial_from_exam(client, remedial_headers, remedial_fixtures):
    """POST /homework/tasks/from-exam 应该成功创建 remedial 类型作业。"""
    resp = await client.post(
        "/api/v1/homework/tasks/from-exam",
        json={
            "exam_id": remedial_fixtures["exam_id"],
            "class_id": remedial_fixtures["class_id"],
        },
        headers=remedial_headers,
    )
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["task_type"] == "remedial"
    assert data["exam_id"] == remedial_fixtures["exam_id"]
    assert data["status"] == "draft"
    assert "补救" in data["title"] or "remedial" in data["title"].lower()
    # content 应该有 question_ids 和 source_exam_id
    content = json.loads(data["content"]) if isinstance(data["content"], str) else data["content"]
    assert "question_ids" in content
    assert content["source_exam_id"] == remedial_fixtures["exam_id"]
    assert "error_threshold" in content


# ── Test 2: 无错题时行为 ──

@pytest.mark.asyncio
async def test_create_remedial_empty_exam(client, remedial_headers, remedial_fixtures, db):
    """没有高错误率题目的考试，应返回空 question_ids 但仍成功创建。"""
    # 创建一个新的"全对"考试
    exam2 = Exam(
        name="全对考试", subject_code="SX", subject_name="数学",
        max_score=100, school_id=remedial_fixtures["school_id"],
        semester="2025-2026-2",
    )
    db.add(exam2)
    await db.flush()
    subject2 = Subject(
        name="数学", code="SX", exam_id=exam2.id,
        school_id=remedial_fixtures["school_id"],
    )
    db.add(subject2)
    await db.flush()
    q = Question(
        name="简单题", question_type="choice", max_score=5.0,
        subject_id=subject2.id, school_id=remedial_fixtures["school_id"],
    )
    db.add(q)
    await db.flush()
    # 所有学生都满分
    for sid in remedial_fixtures["student_ids"]:
        db.add(StudentAnswer(
            student_id=sid, question_id=q.id,
            subject_id=subject2.id, school_id=remedial_fixtures["school_id"],
            exam_id=exam2.id, score=5.0,
        ))
    await db.commit()

    resp = await client.post(
        "/api/v1/homework/tasks/from-exam",
        json={
            "exam_id": exam2.id,
            "class_id": remedial_fixtures["class_id"],
        },
        headers=remedial_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    content = json.loads(data["content"]) if isinstance(data["content"], str) else data["content"]
    assert content["question_ids"] == []


# ── Test 3: content-detail 解析 ──

@pytest.mark.asyncio
async def test_get_content_detail(client, remedial_headers, remedial_fixtures):
    """GET /homework/tasks/{id}/content-detail 应返回题目详情。"""
    # 先创建一个带 content 的作业
    content_json = json.dumps({
        "question_ids": remedial_fixtures["bank_question_ids"][:2],
        "source_exam_id": remedial_fixtures["exam_id"],
        "error_threshold": 0.4,
    })
    create_resp = await client.post(
        "/api/v1/homework/tasks",
        json={
            "title": "内容详情测试",
            "task_type": "post_exam",
            "subject_code": "SX",
            "exam_id": remedial_fixtures["exam_id"],
            "content": content_json,
        },
        headers=remedial_headers,
    )
    assert create_resp.status_code == 201
    task_id = create_resp.json()["id"]

    resp = await client.get(
        f"/api/v1/homework/tasks/{task_id}/content-detail",
        headers=remedial_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "questions" in data
    assert len(data["questions"]) == 2
    # 每个题目应有基本信息
    q = data["questions"][0]
    assert "id" in q
    assert "content_text" in q
    assert "question_type" in q


# ── Test 4: 权限校验 ──

@pytest.mark.asyncio
async def test_remedial_permission_denied(client, observer_headers, remedial_fixtures):
    """observer 角色无 MANAGE_HOMEWORK 权限，应被拒绝。"""
    resp = await client.post(
        "/api/v1/homework/tasks/from-exam",
        json={
            "exam_id": remedial_fixtures["exam_id"],
            "class_id": remedial_fixtures["class_id"],
        },
        headers=observer_headers,
    )
    assert resp.status_code == 403
