"""归属链校验回归测试 — scan/upload-objective + compat/upload-objective。

验证 ownership.py 引入后：
- 跨科目 question 被拒 (question.subject_id != req.subject_id)
- 跨考试 subject 被拒 (subject.exam_id != req.exam_id)
- 正常写入成功
- 缺考路径成功
"""

import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def ownership_data(db):
    """Set up school, exam, two subjects, questions in each."""
    school = School(name="归属链测试校", code="OWN", district="D", api_key_hash="x")
    db.add(school)
    await db.flush()

    exam = Exam(name="期中考试", school_id=school.id, status="draft")
    db.add(exam)
    await db.flush()

    subj_math = Subject(name="数学", code="math", exam_id=exam.id, school_id=school.id)
    subj_chinese = Subject(name="语文", code="chinese", exam_id=exam.id, school_id=school.id)
    db.add_all([subj_math, subj_chinese])
    await db.flush()

    q_math = Question(
        name="数学第1题", subject_id=subj_math.id, question_type="choice",
        max_score=5.0, correct_answer="A", school_id=school.id,
    )
    q_chinese = Question(
        name="语文第1题", subject_id=subj_chinese.id, question_type="choice",
        max_score=5.0, correct_answer="B", school_id=school.id,
    )
    db.add_all([q_math, q_chinese])
    await db.commit()

    # another exam (for cross-exam test)
    exam2 = Exam(name="期末考试", school_id=school.id, status="draft")
    db.add(exam2)
    await db.flush()
    subj_other_exam = Subject(name="数学", code="math2", exam_id=exam2.id, school_id=school.id)
    db.add(subj_other_exam)
    await db.commit()

    user = User(username="owner_tester", display_name="T")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="academic_director",
                    school_id=school.id, is_primary=True))
    await db.commit()

    token = create_access_token({
        "sub": user.id, "role": "academic_director",
        "school_id": school.id,
    })
    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "school_id": school.id,
        "exam_id": exam.id,
        "exam2_id": exam2.id,
        "subj_math_id": subj_math.id,
        "subj_chinese_id": subj_chinese.id,
        "subj_other_exam_id": subj_other_exam.id,
        "q_math_id": q_math.id,
        "q_chinese_id": q_chinese.id,
    }


# ── scan/upload-objective: cross-subject question rejected ──

@pytest.mark.asyncio
async def test_upload_objective_rejects_cross_subject_question(client, ownership_data):
    """数学题 question 提交到语文科目 → 404。"""
    d = ownership_data
    resp = await client.post("/api/v1/scan/upload-objective", json={
        "exam_id": d["exam_id"],
        "subject_id": d["subj_chinese_id"],
        "student_id": "student-001",
        "answers": [{"question_id": d["q_math_id"], "detected_answer": "A"}],
    }, headers=d["headers"])
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ── scan/upload-objective: cross-exam subject rejected ──

@pytest.mark.asyncio
async def test_upload_objective_rejects_cross_exam_subject(client, ownership_data):
    """用 exam1 的 id 但 exam2 的 subject → 404。"""
    d = ownership_data
    resp = await client.post("/api/v1/scan/upload-objective", json={
        "exam_id": d["exam_id"],
        "subject_id": d["subj_other_exam_id"],
        "student_id": "student-001",
        "answers": [],
    }, headers=d["headers"])
    assert resp.status_code == 404
    assert "subject" in resp.json()["detail"].lower()


# ── scan/upload-objective: normal write succeeds ──

@pytest.mark.asyncio
async def test_upload_objective_normal_write(client, ownership_data):
    """正确的 exam→subject→question 链 → 200。"""
    d = ownership_data
    resp = await client.post("/api/v1/scan/upload-objective", json={
        "exam_id": d["exam_id"],
        "subject_id": d["subj_math_id"],
        "student_id": "student-002",
        "answers": [{"question_id": d["q_math_id"], "detected_answer": "A"}],
    }, headers=d["headers"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["student_id"] == "student-002"
    assert len(body["results"]) == 1


# ── scan/upload-objective: absent path succeeds ──

@pytest.mark.asyncio
async def test_upload_objective_absent_path(client, ownership_data):
    """缺考标记 → 200，is_absent=True。"""
    d = ownership_data
    resp = await client.post("/api/v1/scan/upload-objective", json={
        "exam_id": d["exam_id"],
        "subject_id": d["subj_math_id"],
        "student_id": "student-absent",
        "is_absent": True,
    }, headers=d["headers"])
    assert resp.status_code == 200
    assert resp.json()["is_absent"] is True


# ── compat/upload-objective: cross-subject question rejected ──

@pytest.mark.asyncio
async def test_compat_upload_objective_rejects_cross_subject(client, ownership_data):
    """compat 端点同样应拒绝跨科目 question。"""
    d = ownership_data
    resp = await client.post("/api/scan/upload-objective", json={
        "exam_id": d["exam_id"],
        "subject_id": d["subj_chinese_id"],
        "student_id": "student-003",
        "answers": [{"question_id": d["q_math_id"], "detected_answer": "A"}],
    }, headers=d["headers"])
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ── compat/upload-objective: normal write succeeds ──

@pytest.mark.asyncio
async def test_compat_upload_objective_normal(client, ownership_data):
    """compat 端点正常链 → 200 + 正确评分。"""
    d = ownership_data
    resp = await client.post("/api/scan/upload-objective", json={
        "exam_id": d["exam_id"],
        "subject_id": d["subj_math_id"],
        "student_id": "student-004",
        "answers": [{"question_id": d["q_math_id"], "detected_answer": "A"}],
    }, headers=d["headers"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"][0]["is_correct"] is True
    assert body["results"][0]["score"] == 5.0
