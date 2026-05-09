"""错题→知识点聚合→推荐练习 API 测试（TDD-lite：先写 3 个失败测试）。"""
import pytest

from edu_cloud.modules.bank.models import BankQuestion, StudentErrorBook
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def seed_error_book_with_knowledge(db):
    """创建含知识点标注的错题数据：3 道错题覆盖 2 个知识点。含校级用户 headers。"""
    from edu_cloud.models.school import School
    from edu_cloud.models.class_group import ClassGroup
    from edu_cloud.models.student import Student
    from edu_cloud.models.exam import Exam
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole

    school = School(name="推荐测试校", code="RECTEST", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    # 创建绑定学校的用户
    user = User(username="rec_teacher", display_name="推荐老师")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    cls = ClassGroup(name="八年级1班", grade="八年级", grade_number=8, school_id=school.id)
    db.add(cls)
    await db.flush()

    db.add(UserRole(user_id=user.id, role="homeroom_teacher", school_id=school.id,
                    is_primary=True, class_ids=[cls.id]))
    await db.flush()

    student = Student(name="推荐学生A", student_number="R001", school_id=school.id,
                      class_id=cls.id, grade="八年级")
    db.add(student)
    await db.flush()

    exam = Exam(name="单元测试", subject_code="SX", subject_name="数学",
                max_score=100, school_id=school.id, semester="2025-2026-2")
    db.add(exam)
    await db.flush()

    # 3 道题库题：kp-A 出现 2 次错题，kp-B 出现 1 次
    bq1 = BankQuestion(
        school_id=school.id, question_type="choice", max_score=5,
        content_text="1+1=?", difficulty=0.3, knowledge_point_ids=["kp-A"],
    )
    bq2 = BankQuestion(
        school_id=school.id, question_type="fill", max_score=10,
        content_text="2+2=?", difficulty=0.5, knowledge_point_ids=["kp-A", "kp-B"],
    )
    bq3 = BankQuestion(
        school_id=school.id, question_type="choice", max_score=5,
        content_text="3+3=?", difficulty=0.2, knowledge_point_ids=["kp-B"],
    )
    # 额外一道未错的题（同 kp-A，用于推荐）
    bq4 = BankQuestion(
        school_id=school.id, question_type="short_answer", max_score=15,
        content_text="5+5=?", difficulty=0.4, knowledge_point_ids=["kp-A"],
    )
    db.add_all([bq1, bq2, bq3, bq4])
    await db.flush()

    # 学生错题：bq1, bq2, bq3 都做错了
    from edu_cloud.modules.exam.models import Subject, Question
    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()

    q1 = Question(subject_id=subj.id, name="第1题", question_type="choice", max_score=5, school_id=school.id)
    q2 = Question(subject_id=subj.id, name="第2题", question_type="fill", max_score=10, school_id=school.id)
    q3 = Question(subject_id=subj.id, name="第3题", question_type="choice", max_score=5, school_id=school.id)
    db.add_all([q1, q2, q3])
    await db.flush()

    err1 = StudentErrorBook(
        student_id=student.id, question_id=q1.id, bank_question_id=bq1.id,
        exam_id=exam.id, student_score=1, max_score=5, school_id=school.id,
        knowledge_point_ids=["kp-A"], mastery_status="unmastered",
    )
    err2 = StudentErrorBook(
        student_id=student.id, question_id=q2.id, bank_question_id=bq2.id,
        exam_id=exam.id, student_score=3, max_score=10, school_id=school.id,
        knowledge_point_ids=["kp-A", "kp-B"], mastery_status="unmastered",
    )
    err3 = StudentErrorBook(
        student_id=student.id, question_id=q3.id, bank_question_id=bq3.id,
        exam_id=exam.id, student_score=2, max_score=5, school_id=school.id,
        knowledge_point_ids=["kp-B"], mastery_status="practicing",
    )
    db.add_all([err1, err2, err3])
    await db.commit()

    # 生成绑定学校的 JWT
    token = create_access_token({"sub": user.id, "role": "homeroom_teacher"})
    headers = {"Authorization": f"Bearer {token}"}

    return {
        "school_id": school.id,
        "student_id": student.id,
        "exam_id": exam.id,
        "bank_question_ids": [bq1.id, bq2.id, bq3.id, bq4.id],
        "headers": headers,
    }


@pytest.mark.asyncio
async def test_knowledge_summary_aggregation(client, seed_error_book_with_knowledge):
    """知识聚合：kp-A 出现 2 次（err1+err2），kp-B 出现 2 次（err2+err3），按 error_count DESC 排序。"""
    sid = seed_error_book_with_knowledge["student_id"]
    headers = seed_error_book_with_knowledge["headers"]
    resp = await client.get(
        f"/api/v1/bank/error-book/{sid}/knowledge-summary",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 2

    # 两个知识点各出现 2 次（kp-A: err1+err2, kp-B: err2+err3）
    kp_map = {item["knowledge_point_id"]: item for item in data}
    assert "kp-A" in kp_map
    assert "kp-B" in kp_map
    assert kp_map["kp-A"]["error_count"] == 2
    assert kp_map["kp-B"]["error_count"] == 2

    # 每条都有必要字段
    for item in data:
        assert "knowledge_point_id" in item
        assert "error_count" in item
        assert "mastery_status" in item


@pytest.mark.asyncio
async def test_recommended_practice(client, seed_error_book_with_knowledge):
    """推荐练习：返回未做错的同知识点题目，按 difficulty ASC 排序。"""
    sid = seed_error_book_with_knowledge["student_id"]
    headers = seed_error_book_with_knowledge["headers"]
    resp = await client.get(
        f"/api/v1/bank/error-book/{sid}/recommendations",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # 至少推荐了 bq4（同 kp-A 但未做错）
    assert len(data) >= 1
    # 每条有必要字段
    for item in data:
        assert "id" in item
        assert "question_type" in item
        assert "difficulty" in item
        assert "knowledge_point_ids" in item


@pytest.mark.asyncio
async def test_empty_error_book_returns_empty(client, admin_headers, seed_exam_with_results):
    """空错题本：知识聚合和推荐都返回空列表。"""
    # seed_exam_with_results 有学生但无 StudentErrorBook 记录
    sid = seed_exam_with_results["student_ids"][0]

    summary_resp = await client.get(
        f"/api/v1/bank/error-book/{sid}/knowledge-summary",
        headers=admin_headers,
    )
    assert summary_resp.status_code == 200
    assert summary_resp.json() == []

    rec_resp = await client.get(
        f"/api/v1/bank/error-book/{sid}/recommendations",
        headers=admin_headers,
    )
    assert rec_resp.status_code == 200
    assert rec_resp.json() == []
