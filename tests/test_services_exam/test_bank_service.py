import pytest
from edu_cloud.modules.bank.models import BankQuestion, StudentErrorBook
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.models.school import School
from edu_cloud.modules.bank import service as bank_service
from edu_cloud.services.exceptions import NotFoundError


@pytest.mark.asyncio
async def test_list_bank_questions_with_filter(db):
    school = School(name="测试", code="BS01")
    db.add(school)
    await db.flush()

    db.add(BankQuestion(school_id=school.id, question_type="choice", max_score=5, difficulty=0.8, sample_count=100))
    db.add(BankQuestion(school_id=school.id, question_type="essay", max_score=10, difficulty=0.4, sample_count=50))
    db.add(BankQuestion(school_id=school.id, question_type="choice", max_score=5, difficulty=0.3, sample_count=80))
    await db.commit()

    # 按类型
    result = await bank_service.list_bank_questions(db, school_id=school.id, question_type="choice")
    assert len(result) == 2

    # 按难度范围
    result = await bank_service.list_bank_questions(db, school_id=school.id, min_difficulty=0.5)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_error_book_stats(db):
    school = School(name="测试", code="BS02")
    db.add(school)
    await db.flush()
    exam = Exam(name="考试", card_title="考试", school_id=school.id)
    db.add(exam)
    await db.flush()
    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()

    for i, status in enumerate(["unmastered", "unmastered", "unmastered", "practicing", "mastered"]):
        q = Question(subject_id=subj.id, school_id=school.id, name=str(i+1), question_type="essay", max_score=10)
        db.add(q)
        await db.flush()
        db.add(StudentErrorBook(
            school_id=school.id, student_id="stu001", question_id=q.id,
            exam_id=exam.id, student_score=3.0, max_score=10.0,
            mastery_status=status,
        ))
    await db.commit()

    stats = await bank_service.get_error_book_stats(db, student_id="stu001", school_id=school.id)
    assert stats["total"] == 5
    assert stats["unmastered"] == 3
    assert stats["practicing"] == 1
    assert stats["mastered"] == 1


@pytest.mark.asyncio
async def test_get_bank_question_found(db):
    """TG-003: get_bank_question 命中。"""
    school = School(name="测试", code="BS03")
    db.add(school)
    await db.flush()
    bq = BankQuestion(school_id=school.id, question_type="choice", max_score=5, sample_count=10)
    db.add(bq)
    await db.commit()

    result = await bank_service.get_bank_question(db, bank_question_id=bq.id, school_id=school.id)
    assert result.id == bq.id


@pytest.mark.asyncio
async def test_get_bank_question_not_found(db):
    """TG-003: get_bank_question 不存在抛 NotFoundError。"""
    with pytest.raises(NotFoundError):
        await bank_service.get_bank_question(db, bank_question_id="nonexistent", school_id="any")


@pytest.mark.asyncio
async def test_get_student_error_book_with_filters(db):
    """TG-003: get_student_error_book mastery_status + limit 过滤。"""
    school = School(name="测试", code="BS04")
    db.add(school)
    await db.flush()
    exam = Exam(name="考试", card_title="考试", school_id=school.id)
    db.add(exam)
    await db.flush()
    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()

    for i, status in enumerate(["unmastered", "unmastered", "practicing"]):
        q = Question(subject_id=subj.id, school_id=school.id, name=str(i+1), question_type="essay", max_score=10)
        db.add(q)
        await db.flush()
        db.add(StudentErrorBook(
            school_id=school.id, student_id="stu_filter", question_id=q.id,
            exam_id=exam.id, student_score=3.0, max_score=10.0,
            mastery_status=status,
        ))
    await db.commit()

    # 按 mastery_status 过滤
    result = await bank_service.get_student_error_book(
        db, student_id="stu_filter", school_id=school.id, mastery_status="unmastered",
    )
    assert len(result) == 2

    # limit
    result = await bank_service.get_student_error_book(
        db, student_id="stu_filter", school_id=school.id, limit=1,
    )
    assert len(result) == 1


@pytest.mark.asyncio
async def test_get_student_error_book_empty(db):
    """TG-003: 无错题返回空列表。"""
    result = await bank_service.get_student_error_book(
        db, student_id="nonexistent", school_id="any",
    )
    assert result == []


@pytest.mark.asyncio
async def test_bank_question_new_fields_roundtrip(db):
    """S1-A: 5 新字段写入 + 读回完整性验证"""
    school = School(name="测试", code="BS_S1A_01")
    db.add(school)
    await db.flush()

    q = BankQuestion(
        school_id=school.id,
        question_type="essay",
        max_score=10.0,
        sample_count=0,
        source="exam",
        explanation="勾股定理应用题",
        knowledge_point_ids=[101, 102, 103],
        difficulty_level="hard",
        grade_id="00000000-0000-0000-0000-000000000001",
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)

    assert q.source == "exam"
    assert q.explanation == "勾股定理应用题"
    assert q.knowledge_point_ids == [101, 102, 103]
    assert q.difficulty_level == "hard"
    assert q.grade_id == "00000000-0000-0000-0000-000000000001"


@pytest.mark.asyncio
async def test_bank_question_new_fields_all_nullable(db):
    """S1-A: 5 新字段全部可以为 None(不传参数)"""
    school = School(name="测试", code="BS_S1A_02")
    db.add(school)
    await db.flush()

    q = BankQuestion(
        school_id=school.id,
        question_type="choice",
        max_score=5.0,
        sample_count=0,
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)

    assert q.source is None
    assert q.explanation is None
    assert q.knowledge_point_ids is None
    assert q.difficulty_level is None
    assert q.grade_id is None


@pytest.mark.asyncio
async def test_bank_question_new_fields_visible_via_service(db):
    """S1-A 入口级验证(R1 F-S1A-02 修正):经 bank_service.get_bank_question 读回,
    验证新字段在 service 层序列化完整,不只是 ORM 属性可达。

    走 service 的理由:防止 Task 1 改完 ORM 但 bank_service 的 SELECT 列投影
    /Pydantic response model 漏了新字段这种"ORM 层绿但 service 层断"的隐患。
    """
    school = School(name="测试", code="BS_S1A_03")
    db.add(school)
    await db.flush()

    q = BankQuestion(
        school_id=school.id,
        question_type="essay",
        max_score=10.0,
        sample_count=0,
        source="textbook",
        explanation="教材例题 2-3",
        knowledge_point_ids=[201, 202],
        difficulty_level="medium",
        grade_id="00000000-0000-0000-0000-000000000002",
    )
    db.add(q)
    await db.commit()
    qid = q.id

    # 经 service 层读回(不是直接 SQLAlchemy query)
    # R2 F-S1A-R2-01 修正:keyword 参数是 bank_question_id(见 src/edu_cloud/modules/bank/service.py:13),
    # 不是 question_id
    retrieved = await bank_service.get_bank_question(db, bank_question_id=qid, school_id=school.id)
    assert retrieved is not None, "service 层找不到刚写入的 BankQuestion"
    assert retrieved.id == qid
    # 新字段都能从 service 层读出(若 service 的 select_from 缺列或 response model 漏字段 → 任一 AttributeError/None 捕获)
    assert retrieved.source == "textbook"
    assert retrieved.explanation == "教材例题 2-3"
    assert retrieved.knowledge_point_ids == [201, 202]
    assert retrieved.difficulty_level == "medium"
    assert retrieved.grade_id == "00000000-0000-0000-0000-000000000002"
