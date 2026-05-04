import pytest
from edu_cloud.models.school import School
from edu_cloud.models.student import Class, Student
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.knowledge.models import QuestionKnowledgePoint
from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode
from edu_cloud.modules.profile.models import StudentExamSnapshot, StudentKnowledgeMastery, StudentErrorPattern
from edu_cloud.modules.bank.models import StudentErrorBook
from edu_cloud.modules.grading.models import GradingResult, GradingTask
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.modules.pipeline.service import (
    generate_exam_snapshots, update_knowledge_mastery,
    update_error_patterns, run_full_pipeline,
)
from sqlalchemy import select, func


async def _setup_full_exam(db):
    """创建完整的考试数据：学校+班级+学生+考试+题目+知识点+成绩。"""
    school = School(name="测试学校", code="PP01")
    db.add(school)
    await db.flush()

    cls = Class(name="高二(1)班", grade="高二", school_id=school.id)
    db.add(cls)
    await db.flush()

    students = []
    for i in range(5):
        s = Student(name=f"学生{i+1}", student_number=f"PP{i:04d}", class_id=cls.id, school_id=school.id)
        db.add(s)
        students.append(s)
    await db.flush()

    exam = Exam(name="期中考试", card_title="期中", school_id=school.id, status="completed")
    db.add(exam)
    await db.flush()

    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()

    # 2 道题，各关联 1 个知识点
    from datetime import datetime, timezone
    kp1 = ConceptGraphNode(id="MATH_FUNC", name="函数", knowledge_level="L1", primary_module="M1", synced_at=datetime.now(timezone.utc), course_code="SX")
    kp2 = ConceptGraphNode(id="MATH_TRIG", name="三角函数", knowledge_level="L1", primary_module="M1", synced_at=datetime.now(timezone.utc), course_code="SX")
    db.add_all([kp1, kp2])
    await db.flush()

    q1 = Question(subject_id=subj.id, school_id=school.id, name="1", question_type="essay", max_score=10)
    q2 = Question(subject_id=subj.id, school_id=school.id, name="2", question_type="essay", max_score=10)
    db.add_all([q1, q2])
    await db.flush()

    db.add(QuestionKnowledgePoint(question_id=q1.id, concept_id=kp1.id, is_primary=True))
    db.add(QuestionKnowledgePoint(question_id=q2.id, concept_id=kp2.id, is_primary=True))
    await db.flush()

    # 5 个学生的成绩: (q1_score, q2_score)
    # totals: 14, 19, 8, 14, 17
    scores = [(8, 6), (10, 9), (5, 3), (7, 7), (9, 8)]
    for student, (s1, s2) in zip(students, scores):
        db.add(StudentAnswer(
            exam_id=exam.id, subject_id=subj.id, student_id=student.id,
            question_id=q1.id, school_id=school.id, score=float(s1),
        ))
        db.add(StudentAnswer(
            exam_id=exam.id, subject_id=subj.id, student_id=student.id,
            question_id=q2.id, school_id=school.id, score=float(s2),
        ))
    await db.commit()
    return school, exam, students, subj


@pytest.mark.asyncio
async def test_generate_exam_snapshots(db):
    school, exam, students, subj = await _setup_full_exam(db)

    created = await generate_exam_snapshots(db, exam_id=exam.id, school_id=school.id)
    assert created == 5  # 5 个学生

    result = await db.execute(
        select(StudentExamSnapshot)
        .where(StudentExamSnapshot.exam_id == exam.id)
        .order_by(StudentExamSnapshot.grade_rank)
    )
    snaps = result.scalars().all()
    assert len(snaps) == 5
    assert snaps[0].grade_rank == 1  # 最高分第 1 名
    assert snaps[0].total_score > snaps[-1].total_score

    # DF-005: class_rank/class_size 已计算
    assert snaps[0].class_rank is not None
    assert snaps[0].class_size == 5  # 同班 5 人
    assert snaps[0].grade_size == 5

    # DF-005: knowledge_scores 已计算
    top_snap = snaps[0]
    assert top_snap.knowledge_scores is not None
    assert "MATH_FUNC" in top_snap.knowledge_scores or "MATH_TRIG" in top_snap.knowledge_scores

    # DF-005: exam_date 已填充
    assert top_snap.exam_date is not None

    # B2-01: 幂等 — 第二次运行 upsert（返回 5 = 更新数，不是 0）
    created2 = await generate_exam_snapshots(db, exam_id=exam.id, school_id=school.id)
    assert created2 == 5  # upsert: 更新已有记录
    # 但数据库记录数不变
    count_result = await db.execute(
        select(func.count()).select_from(StudentExamSnapshot).where(StudentExamSnapshot.exam_id == exam.id)
    )
    assert count_result.scalar() == 5


@pytest.mark.asyncio
async def test_update_knowledge_mastery(db):
    school, exam, students, subj = await _setup_full_exam(db)

    updated = await update_knowledge_mastery(db, exam_id=exam.id, school_id=school.id)
    assert updated > 0  # student × kp 条记录

    # 验证某学生的掌握度
    result = await db.execute(
        select(StudentKnowledgeMastery).where(
            StudentKnowledgeMastery.student_id == students[0].id,
        )
    )
    masteries = result.scalars().all()
    assert len(masteries) == 2  # 2 个知识点
    for m in masteries:
        assert 0 <= m.mastery_level <= 1
        assert m.attempt_count >= 1


@pytest.mark.asyncio
async def test_update_error_patterns(db):
    """DF-006: update_error_patterns 从错题本聚合错误模式。"""
    school, exam, students, subj = await _setup_full_exam(db)

    # 先手动创建一些错题记录
    result = await db.execute(
        select(Question).where(Question.subject_id == subj.id)
    )
    questions = result.scalars().all()
    q1, q2 = questions[0], questions[1]

    # 学生0: q1得8分(满10), q2得6分(满10) → 两个错题
    for stu, q, score in [
        (students[0], q1, 8.0), (students[0], q2, 6.0),
        (students[2], q1, 5.0),
    ]:
        db.add(StudentErrorBook(
            school_id=school.id, student_id=stu.id, question_id=q.id,
            exam_id=exam.id, student_score=score, max_score=10.0,
            error_type="计算错误", mastery_status="unmastered",
        ))
    await db.commit()

    updated = await update_error_patterns(db, exam_id=exam.id, school_id=school.id)
    assert updated >= 2  # 至少 2 个学生有错题

    # 验证学生0的错误模式
    result = await db.execute(
        select(StudentErrorPattern).where(
            StudentErrorPattern.student_id == students[0].id,
            StudentErrorPattern.subject_code == "SX",
        )
    )
    pattern = result.scalar_one()
    assert pattern.total_errors == 2
    assert pattern.exam_count == 1
    assert "计算错误" in pattern.error_distribution


@pytest.mark.asyncio
async def test_run_full_pipeline(db):
    school, exam, students, subj = await _setup_full_exam(db)

    results = await run_full_pipeline(db, exam_id=exam.id, school_id=school.id)
    assert results["bank_questions"] >= 2
    assert results["exam_snapshots"] == 5
    assert results["knowledge_mastery"] > 0
    assert "error_patterns" in results  # DF-006

    # B2-01/B2-03: 幂等 — 第二次运行不重复累加
    results2 = await run_full_pipeline(db, exam_id=exam.id, school_id=school.id)
    assert results2["bank_questions"] == 0  # savepoint skip
    assert results2["knowledge_mastery"] == 0  # B2-01: last_exam_id 幂等
    # snapshots 现在是 upsert，返回 5（更新数）但不新增行
    # error_books 是 savepoint skip
    assert results2["error_books"] == 0

    # B2-01: 验证 mastery attempt_count 没有因为重跑而翻倍
    mastery_check = await db.execute(
        select(StudentKnowledgeMastery).where(
            StudentKnowledgeMastery.student_id == students[0].id,
        )
    )
    for m in mastery_check.scalars().all():
        assert m.attempt_count == 1  # 只计入一次考试


@pytest.mark.asyncio
async def test_snapshot_uses_effective_score(db):
    """B2-02: generate_exam_snapshots 使用 effective_score（考虑 TeacherReview 改分）。"""
    school = School(name="测试", code="PP_EFF")
    db.add(school)
    await db.flush()
    cls = Class(name="班级", grade="高二", school_id=school.id)
    db.add(cls)
    await db.flush()
    stu = Student(name="学生1", student_number="EFF001", class_id=cls.id, school_id=school.id)
    db.add(stu)
    await db.flush()

    exam = Exam(name="考试", card_title="考试", school_id=school.id, status="completed")
    db.add(exam)
    await db.flush()
    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()
    q = Question(subject_id=subj.id, school_id=school.id, name="1", question_type="essay", max_score=10)
    db.add(q)
    await db.flush()

    # 学生答题：原始 3 分
    sa = StudentAnswer(
        exam_id=exam.id, subject_id=subj.id, student_id=stu.id,
        question_id=q.id, school_id=school.id, score=3.0,
    )
    db.add(sa)
    await db.flush()

    # AI 给 3 分，老师改成 9 分
    user = User(username="t_eff", display_name="教师")
    user.set_password("123456")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="teacher", school_id=school.id, is_primary=True))
    await db.flush()
    gt = GradingTask(subject_id=subj.id, school_id=school.id, created_by=user.id)
    db.add(gt)
    await db.flush()
    gr = GradingResult(
        ai_task_id=gt.id, answer_id=sa.id, question_id=q.id,
        school_id=school.id, ai_score=3.0, final_score=9.0, max_score=10.0,
        status="confirmed", source="ai_override", reviewer_id=user.id,
    )
    db.add(gr)
    await db.commit()

    # 生成快照 — 应使用 effective_score=9，而非原始 3
    await generate_exam_snapshots(db, exam_id=exam.id, school_id=school.id)

    snap_result = await db.execute(
        select(StudentExamSnapshot).where(
            StudentExamSnapshot.student_id == stu.id,
            StudentExamSnapshot.exam_id == exam.id,
        )
    )
    snap = snap_result.scalar_one()
    assert snap.total_score == 9.0  # B2-02: effective_score, not 3.0


@pytest.mark.asyncio
async def test_mastery_uses_effective_score(db):
    """B2-02: update_knowledge_mastery 使用 effective_score。"""
    school = School(name="测试", code="PP_MEFF")
    db.add(school)
    await db.flush()
    cls = Class(name="班级", grade="高二", school_id=school.id)
    db.add(cls)
    await db.flush()
    stu = Student(name="学生1", student_number="MEFF01", class_id=cls.id, school_id=school.id)
    db.add(stu)
    await db.flush()

    exam = Exam(name="考试", card_title="考试", school_id=school.id, status="completed")
    db.add(exam)
    await db.flush()
    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()
    from datetime import datetime, timezone
    kp = ConceptGraphNode(id="M_EFF_KP", name="测试KP", knowledge_level="L1", primary_module="M1", synced_at=datetime.now(timezone.utc), course_code="SX")
    db.add(kp)
    await db.flush()
    q = Question(subject_id=subj.id, school_id=school.id, name="1", question_type="essay", max_score=10)
    db.add(q)
    await db.flush()
    db.add(QuestionKnowledgePoint(question_id=q.id, concept_id=kp.id, is_primary=True))

    sa = StudentAnswer(
        exam_id=exam.id, subject_id=subj.id, student_id=stu.id,
        question_id=q.id, school_id=school.id, score=3.0,
    )
    db.add(sa)
    await db.flush()

    # AI 给 3 分，老师改 9 分 → effective = 9/10 = 0.9
    user = User(username="t_meff", display_name="教师")
    user.set_password("123456")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="teacher", school_id=school.id, is_primary=True))
    await db.flush()
    gt = GradingTask(subject_id=subj.id, school_id=school.id, created_by=user.id)
    db.add(gt)
    await db.flush()
    gr = GradingResult(
        ai_task_id=gt.id, answer_id=sa.id, question_id=q.id,
        school_id=school.id, ai_score=3.0, final_score=9.0, max_score=10.0,
        status="confirmed", source="ai_override", reviewer_id=user.id,
    )
    db.add(gr)
    await db.commit()

    await update_knowledge_mastery(db, exam_id=exam.id, school_id=school.id)

    mastery_result = await db.execute(
        select(StudentKnowledgeMastery).where(
            StudentKnowledgeMastery.student_id == stu.id,
            StudentKnowledgeMastery.concept_id == kp.id,
        )
    )
    mastery = mastery_result.scalar_one()
    # effective = 9/10 = 0.9, 不是 3/10 = 0.3
    assert mastery.mastery_level == pytest.approx(0.9, abs=0.01)


@pytest.mark.asyncio
async def test_mastery_idempotent_same_exam(db):
    """B2-01: update_knowledge_mastery 同一考试重跑不累加。"""
    school, exam, students, subj = await _setup_full_exam(db)

    updated1 = await update_knowledge_mastery(db, exam_id=exam.id, school_id=school.id)
    assert updated1 > 0

    # 记录 attempt_count
    m_result = await db.execute(
        select(StudentKnowledgeMastery).where(StudentKnowledgeMastery.student_id == students[0].id)
    )
    counts_before = {m.concept_id: m.attempt_count for m in m_result.scalars().all()}

    # 重跑
    updated2 = await update_knowledge_mastery(db, exam_id=exam.id, school_id=school.id)
    assert updated2 == 0  # B2-01: last_exam_id 相同，跳过

    # attempt_count 不变
    m_result2 = await db.execute(
        select(StudentKnowledgeMastery).where(StudentKnowledgeMastery.student_id == students[0].id)
    )
    for m in m_result2.scalars().all():
        assert m.attempt_count == counts_before[m.concept_id]


@pytest.mark.asyncio
async def test_error_patterns_idempotent(db):
    """B2-01: update_error_patterns 同一考试重跑不重复累加。"""
    school, exam, students, subj = await _setup_full_exam(db)

    result = await db.execute(select(Question).where(Question.subject_id == subj.id))
    questions = result.scalars().all()

    db.add(StudentErrorBook(
        school_id=school.id, student_id=students[0].id, question_id=questions[0].id,
        exam_id=exam.id, student_score=5.0, max_score=10.0,
        error_type="计算错误", mastery_status="unmastered",
    ))
    await db.commit()

    await update_error_patterns(db, exam_id=exam.id, school_id=school.id)

    p_result = await db.execute(
        select(StudentErrorPattern).where(StudentErrorPattern.student_id == students[0].id)
    )
    pattern = p_result.scalar_one()
    assert pattern.total_errors == 1
    assert pattern.exam_count == 1

    # 重跑 — 不应累加
    await update_error_patterns(db, exam_id=exam.id, school_id=school.id)

    p_result2 = await db.execute(
        select(StudentErrorPattern).where(StudentErrorPattern.student_id == students[0].id)
    )
    pattern2 = p_result2.scalar_one()
    assert pattern2.total_errors == 1  # B2-01: 不变
    assert pattern2.exam_count == 1  # B2-01: 不变


@pytest.mark.asyncio
async def test_error_patterns_cross_exam_accumulates(db):
    """B2-01 Round 3: 两场考试后 error_patterns 正确累积。"""
    school = School(name="测试", code="PP_CROSS")
    db.add(school)
    await db.flush()
    cls = Class(name="班级", grade="高二", school_id=school.id)
    db.add(cls)
    await db.flush()
    stu = Student(name="学生1", student_number="CROSS01", class_id=cls.id, school_id=school.id)
    db.add(stu)
    await db.flush()

    # 考试 1
    exam1 = Exam(name="期中", card_title="期中", school_id=school.id, status="completed")
    db.add(exam1)
    await db.flush()
    subj1 = Subject(exam_id=exam1.id, name="数学", code="SX", school_id=school.id)
    db.add(subj1)
    await db.flush()
    q1 = Question(subject_id=subj1.id, school_id=school.id, name="1", question_type="essay", max_score=10)
    db.add(q1)
    await db.flush()
    db.add(StudentErrorBook(
        school_id=school.id, student_id=stu.id, question_id=q1.id,
        exam_id=exam1.id, student_score=3.0, max_score=10.0,
        error_type="计算错误", mastery_status="unmastered",
    ))
    await db.commit()

    await update_error_patterns(db, exam_id=exam1.id, school_id=school.id)

    # 考试 2
    exam2 = Exam(name="期末", card_title="期末", school_id=school.id, status="completed")
    db.add(exam2)
    await db.flush()
    subj2 = Subject(exam_id=exam2.id, name="数学", code="SX", school_id=school.id)
    db.add(subj2)
    await db.flush()
    q2 = Question(subject_id=subj2.id, school_id=school.id, name="1", question_type="essay", max_score=10)
    q3 = Question(subject_id=subj2.id, school_id=school.id, name="2", question_type="essay", max_score=10)
    db.add_all([q2, q3])
    await db.flush()
    db.add(StudentErrorBook(
        school_id=school.id, student_id=stu.id, question_id=q2.id,
        exam_id=exam2.id, student_score=4.0, max_score=10.0,
        error_type="概念混淆", mastery_status="unmastered",
    ))
    db.add(StudentErrorBook(
        school_id=school.id, student_id=stu.id, question_id=q3.id,
        exam_id=exam2.id, student_score=2.0, max_score=10.0,
        error_type="计算错误", mastery_status="unmastered",
    ))
    await db.commit()

    await update_error_patterns(db, exam_id=exam2.id, school_id=school.id)

    p_result = await db.execute(
        select(StudentErrorPattern).where(
            StudentErrorPattern.student_id == stu.id,
            StudentErrorPattern.subject_code == "SX",
        )
    )
    pattern = p_result.scalar_one()
    assert pattern.total_errors == 3  # 1 from exam1 + 2 from exam2
    assert pattern.exam_count == 2  # 2 distinct exams
    assert "计算错误" in pattern.error_distribution
    assert "概念混淆" in pattern.error_distribution
