import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingResult
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode
from edu_cloud.modules.profile.models import StudentKnowledgeMastery, StudentErrorPattern
from tests.conftest import *  # noqa


@pytest.fixture
async def school_admin_headers(db, seed_school):
    school, _ = seed_school
    user = User(username="advanced_principal", display_name="校长")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="principal", school_id=school.id, is_primary=True))
    await db.commit()
    token = create_access_token({"sub": user.id, "role": "principal"})
    return {"Authorization": f"Bearer {token}"}


async def _seed_knowledge_exam(db, seed_school):
    school, _ = seed_school
    cls = Class(name="高一(1)班", grade="高一", grade_number=10, school_id=school.id)
    db.add(cls)
    await db.flush()
    stu = Student(name="测试生", student_number="K001", class_id=cls.id, school_id=school.id, grade="高一")
    db.add(stu)
    await db.flush()
    exam = Exam(name="知识点测试", status="completed", school_id=school.id)
    db.add(exam)
    await db.flush()
    subj = Subject(name="生物", code="biology", exam_id=exam.id, school_id=school.id)
    db.add(subj)
    await db.flush()
    q = Question(name="1", question_type="essay", max_score=10, subject_id=subj.id, school_id=school.id)
    db.add(q)
    await db.flush()

    # 创建 ConceptGraphNode + QuestionKnowledgePoint，使 JOIN 查询有实际数据
    from datetime import datetime, timezone
    from edu_cloud.modules.knowledge.models import QuestionKnowledgePoint

    node1 = ConceptGraphNode(
        id="BIO_SR_CP_M1_PHOTOSYNTHESIS", name="光合作用", course_code="biology",
        node_type="concept", knowledge_level="L1", primary_module="M1",
        synced_at=datetime.now(timezone.utc),
    )
    node2 = ConceptGraphNode(
        id="BIO_SR_CP_M1_CELL_DIVISION", name="细胞分裂", course_code="biology",
        node_type="concept", knowledge_level="L1", primary_module="M1",
        synced_at=datetime.now(timezone.utc),
    )
    db.add_all([node1, node2])
    await db.flush()

    qkp1 = QuestionKnowledgePoint(question_id=q.id, concept_id="BIO_SR_CP_M1_PHOTOSYNTHESIS")
    qkp2 = QuestionKnowledgePoint(question_id=q.id, concept_id="BIO_SR_CP_M1_CELL_DIVISION")
    db.add_all([qkp1, qkp2])
    await db.flush()

    sa = StudentAnswer(exam_id=exam.id, subject_id=subj.id, student_id=stu.id, question_id=q.id, school_id=school.id)
    db.add(sa)
    await db.flush()
    gr = GradingResult(
        answer_id=sa.id, question_id=q.id, school_id=school.id,
        final_score=6.0, max_score=10.0, status="confirmed", source="ai",
        ai_raw_response={"details": [{"subQuestion": "(1)", "blanks": [
            {"index": 1, "answer": "错误", "score": 0, "fullScore": 5, "correct": False,
             "reason": "概念混淆：细胞分裂与减数分裂混淆"},
        ]}]},
    )
    db.add(gr)
    await db.commit()
    return exam, subj, stu, cls


@pytest.mark.asyncio
async def test_class_knowledge_returns_structure(client, school_admin_headers, seed_school, db):
    exam, subj, _, _ = await _seed_knowledge_exam(db, seed_school)
    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/class-knowledge",
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "knowledge_points" in data
    assert "classes" in data
    # 值级断言：seed 数据通过 QKP 关联了 2 个 concept
    assert len(data["knowledge_points"]) == 2
    assert "BIO_SR_CP_M1_PHOTOSYNTHESIS" in data["knowledge_points"]
    assert "BIO_SR_CP_M1_CELL_DIVISION" in data["knowledge_points"]
    assert len(data["classes"]) >= 1
    cls = data["classes"][0]
    assert len(cls["mastery"]) == 2
    for m in cls["mastery"]:
        assert 0 <= m["rate"] <= 1
        assert m["kp_id"] in ("BIO_SR_CP_M1_PHOTOSYNTHESIS", "BIO_SR_CP_M1_CELL_DIVISION")
        assert m["name"] in ("光合作用", "细胞分裂")


@pytest.mark.asyncio
async def test_class_error_patterns_returns_structure(client, school_admin_headers, seed_school, db):
    exam, _, _, _ = await _seed_knowledge_exam(db, seed_school)
    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/class-error-patterns",
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "error_types" in data
    assert "classes" in data
    # F004: 值级断言 — seed 数据有"概念混淆"错因
    assert len(data["error_types"]) >= 1
    assert "概念混淆" in data["error_types"]
    assert len(data["classes"]) >= 1
    cls = data["classes"][0]
    assert "概念混淆" in cls["distribution"]
    assert cls["distribution"]["概念混淆"] > 0


@pytest.mark.asyncio
async def test_student_ai_diagnosis_with_mastery(client, school_admin_headers, seed_school, db):
    """F004 加固：seed mastery + error pattern 数据，断言诊断文本包含具体知识点。"""
    exam, subj, stu, _ = await _seed_knowledge_exam(db, seed_school)
    school, _ = seed_school

    from datetime import datetime, timezone
    kp = ConceptGraphNode(
        id="photosynthesis", name="光合作用", course_code="biology",
        node_type="concept", knowledge_level="L1", primary_module="M1",
        synced_at=datetime.now(timezone.utc),
    )
    db.add(kp)
    await db.flush()

    mastery = StudentKnowledgeMastery(
        student_id=stu.id, concept_id=kp.id, school_id=school.id,
        mastery_level=0.35, trend="declining", recent_scores=[0.5, 0.4, 0.35],
        last_exam_id=exam.id,
    )
    db.add(mastery)

    ep = StudentErrorPattern(
        student_id=stu.id, subject_code="biology", school_id=school.id,
        error_distribution={"概念混淆": 0.6, "计算错误": 0.4},
        total_errors=10, exam_count=1,
    )
    db.add(ep)
    await db.commit()

    resp = await client.get(
        f"/api/v1/profile/students/{stu.id}/ai-diagnosis",
        params={"exam_id": exam.id},
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "declining" in [d["trend"] for d in data["declining"]]
    assert len(data["declining"]) >= 1
    assert data["declining"][0]["mastery_level"] == 0.35
    assert len(data["weak_points"]) >= 1
    assert "掌握率" in data["summary"] or "下降" in data["summary"]
    assert "概念混淆" in data["summary"]
    assert len(data["error_patterns"]) >= 1
    assert data["error_patterns"][0]["subject_code"] == "biology"
