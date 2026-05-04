import pytest
from edu_cloud.modules.profile.models import StudentExamSnapshot, StudentKnowledgeMastery, StudentErrorPattern
from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode
from edu_cloud.models.exam import Exam
from edu_cloud.models.school import School


@pytest.mark.asyncio
async def test_create_exam_snapshot(db):
    school = School(name="测试", code="PF01")
    db.add(school)
    await db.flush()
    exam = Exam(name="期中", card_title="期中", school_id=school.id)
    db.add(exam)
    await db.flush()

    snap = StudentExamSnapshot(
        school_id=school.id, student_id="stu001", exam_id=exam.id,
        subject_code="SX", total_score=85.0, max_score=150.0,
        score_rate=85.0/150.0, class_rank=3, grade_rank=15,
        class_size=45, grade_size=320,
        knowledge_scores={"MATH_FUNC": {"score": 25, "max": 30, "rate": 0.83}},
    )
    db.add(snap)
    await db.commit()
    assert snap.id is not None
    assert snap.knowledge_scores["MATH_FUNC"]["rate"] == 0.83


@pytest.mark.asyncio
async def test_create_knowledge_mastery(db):
    from datetime import datetime, timezone
    kp = ConceptGraphNode(id="MATH_FUNC", name="函数", knowledge_level="L1", primary_module="M1", synced_at=datetime.now(timezone.utc), course_code="SX")
    db.add(kp)
    await db.flush()

    school = School(name="测试", code="PF02")
    db.add(school)
    await db.flush()

    mastery = StudentKnowledgeMastery(
        school_id=school.id, student_id="stu001",
        concept_id=kp.id, mastery_level=0.75,
        confidence=0.8, attempt_count=10, correct_count=7,
        trend="improving", recent_scores=[0.6, 0.7, 0.8, 0.75, 0.8],
    )
    db.add(mastery)
    await db.commit()
    assert mastery.trend == "improving"


@pytest.mark.asyncio
async def test_create_error_pattern(db):
    school = School(name="测试", code="PF03")
    db.add(school)
    await db.flush()

    pattern = StudentErrorPattern(
        school_id=school.id, student_id="stu001", subject_code="SX",
        error_distribution={"计算错误": 0.4, "概念混淆": 0.3, "审题失误": 0.2, "未作答": 0.1},
        careless_rate=0.15, total_errors=20, exam_count=4,
    )
    db.add(pattern)
    await db.commit()
    assert pattern.error_distribution["计算错误"] == 0.4


@pytest.mark.asyncio
async def test_snapshot_unique_per_student_exam_subject(db):
    school = School(name="测试", code="PF04")
    db.add(school)
    await db.flush()
    exam = Exam(name="期中", card_title="期中", school_id=school.id)
    db.add(exam)
    await db.flush()

    db.add(StudentExamSnapshot(
        school_id=school.id, student_id="stu001", exam_id=exam.id,
        subject_code="SX", total_score=80, max_score=150, score_rate=0.53,
    ))
    await db.commit()

    from sqlalchemy.exc import IntegrityError
    db.add(StudentExamSnapshot(
        school_id=school.id, student_id="stu001", exam_id=exam.id,
        subject_code="SX", total_score=85, max_score=150, score_rate=0.57,
    ))
    with pytest.raises(IntegrityError):
        await db.commit()
