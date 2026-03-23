import pytest
from edu_cloud.models.school import School
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import AIGradingResult, GradingTask, TeacherReview
from edu_cloud.modules.bank.models import BankQuestion, StudentErrorBook
from edu_cloud.modules.pipeline.service import populate_bank_questions, populate_error_books, _get_effective_score, _compute_question_stats
from sqlalchemy import select, func


async def _setup_exam_with_scores(db):
    school = School(name="测试学校", code="DP01")
    db.add(school)
    await db.flush()

    exam = Exam(name="期中考试", card_title="期中", school_id=school.id, status="completed")
    db.add(exam)
    await db.flush()

    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()

    q1 = Question(subject_id=subj.id, school_id=school.id, name="1", question_type="objective", max_score=5, correct_answer="A")
    q2 = Question(subject_id=subj.id, school_id=school.id, name="2", question_type="subjective", max_score=10)
    db.add_all([q1, q2])
    await db.flush()

    # 5 个学生答题
    for i, (s1, s2) in enumerate([(5, 8), (5, 3), (3, 7), (4, 10), (0, 5)]):
        sa1 = StudentAnswer(
            exam_id=exam.id, subject_id=subj.id, student_id=f"stu{i:03d}",
            question_id=q1.id, school_id=school.id, score=float(s1),
            detected_answer="A" if s1 == 5 else "C",
        )
        sa2 = StudentAnswer(
            exam_id=exam.id, subject_id=subj.id, student_id=f"stu{i:03d}",
            question_id=q2.id, school_id=school.id, score=float(s2),
        )
        db.add_all([sa1, sa2])
    await db.commit()
    return school, exam


@pytest.mark.asyncio
async def test_populate_bank_questions(db):
    school, exam = await _setup_exam_with_scores(db)

    created = await populate_bank_questions(db, exam_id=exam.id, school_id=school.id)
    assert created == 2  # 2 道题

    # 验证统计属性
    result = await db.execute(select(BankQuestion).where(BankQuestion.school_id == school.id))
    bqs = result.scalars().all()
    assert len(bqs) == 2

    obj_bq = next(bq for bq in bqs if bq.question_type == "objective")
    assert obj_bq.sample_count == 5
    # TG-004: 精确断言
    # 选择题分数: [5, 5, 3, 4, 0], max=5 → difficulty = (5+5+3+4+0)/(5*5) = 17/25 = 0.68
    assert obj_bq.difficulty == pytest.approx(0.68, abs=0.01)
    # common_errors: detected_answers = [A, A, C, C, C] → A:2/5=0.4, C:3/5=0.6
    assert obj_bq.common_errors is not None
    assert "C" in obj_bq.common_errors
    assert obj_bq.common_errors["C"] == pytest.approx(0.6, abs=0.01)

    subj_bq = next(bq for bq in bqs if bq.question_type == "subjective")
    assert subj_bq.sample_count == 5
    # 主观题分数: [8, 3, 7, 10, 5], max=10 → difficulty = 33/50 = 0.66
    assert subj_bq.difficulty == pytest.approx(0.66, abs=0.01)
    assert subj_bq.common_errors is None  # 主观题无 detected_answer

    # 幂等 (DF-007)
    created2 = await populate_bank_questions(db, exam_id=exam.id, school_id=school.id)
    assert created2 == 0


@pytest.mark.asyncio
async def test_populate_error_books(db):
    school, exam = await _setup_exam_with_scores(db)

    # 先入库题库
    await populate_bank_questions(db, exam_id=exam.id, school_id=school.id)

    created = await populate_error_books(db, exam_id=exam.id, school_id=school.id)
    assert created > 0  # 有错题

    result = await db.execute(
        select(func.count()).select_from(StudentErrorBook).where(StudentErrorBook.school_id == school.id)
    )
    total = result.scalar()
    assert total == created

    # 验证所有错题的分数 < 满分
    errors = await db.execute(select(StudentErrorBook).where(StudentErrorBook.school_id == school.id))
    for eb in errors.scalars().all():
        assert eb.student_score < eb.max_score

    # 幂等 (DF-007)
    created2 = await populate_error_books(db, exam_id=exam.id, school_id=school.id)
    assert created2 == 0


@pytest.mark.asyncio
async def test_effective_score_with_teacher_review(db):
    """DF-002: 错题收集使用有效分数（考虑 TeacherReview 改分）。"""
    school = School(name="测试", code="DP02")
    db.add(school)
    await db.flush()

    exam = Exam(name="考试", card_title="考试", school_id=school.id, status="completed")
    db.add(exam)
    await db.flush()

    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()

    q = Question(subject_id=subj.id, school_id=school.id, name="1", question_type="subjective", max_score=10)
    db.add(q)
    await db.flush()

    # 学生答题：AI 给 3 分，但老师改成 10 分（满分）
    sa = StudentAnswer(
        exam_id=exam.id, subject_id=subj.id, student_id="stu_review",
        question_id=q.id, school_id=school.id, score=3.0,
    )
    db.add(sa)
    await db.flush()

    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    user = User(username="t1", display_name="教师")
    user.set_password("123456")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="teacher", school_id=school.id, is_primary=True))
    await db.flush()

    gt = GradingTask(subject_id=subj.id, school_id=school.id, created_by=user.id)
    db.add(gt)
    await db.flush()

    ai_result = AIGradingResult(
        task_id=gt.id, answer_id=sa.id, question_id=q.id,
        school_id=school.id, score=3.0, max_score=10.0,
        review_status="overridden",
    )
    db.add(ai_result)
    await db.flush()

    review = TeacherReview(
        result_id=ai_result.id, reviewer_id=user.id,
        school_id=school.id, action="override", adjusted_score=10.0,
    )
    db.add(review)
    await db.commit()

    # 题库入库
    await populate_bank_questions(db, exam_id=exam.id, school_id=school.id)

    # 错题收集 — 老师改成满分，不应该收集为错题
    created = await populate_error_books(db, exam_id=exam.id, school_id=school.id)
    assert created == 0  # 有效分 = 10（满分），不是错题


@pytest.mark.asyncio
async def test_effective_score_ai_only(db):
    """TG-004: _get_effective_score 分支 2 — 仅 AI 分数（无 TeacherReview）。"""
    school = School(name="测试", code="DP03")
    db.add(school)
    await db.flush()
    exam = Exam(name="考试", card_title="考试", school_id=school.id, status="completed")
    db.add(exam)
    await db.flush()
    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()
    q = Question(subject_id=subj.id, school_id=school.id, name="1", question_type="subjective", max_score=10)
    db.add(q)
    await db.flush()

    sa = StudentAnswer(
        exam_id=exam.id, subject_id=subj.id, student_id="stu_ai",
        question_id=q.id, school_id=school.id, score=2.0,
    )
    db.add(sa)
    await db.flush()

    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    user = User(username="t2", display_name="教师")
    user.set_password("123456")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="teacher", school_id=school.id, is_primary=True))
    await db.flush()

    gt = GradingTask(subject_id=subj.id, school_id=school.id, created_by=user.id)
    db.add(gt)
    await db.flush()

    ai_result = AIGradingResult(
        task_id=gt.id, answer_id=sa.id, question_id=q.id,
        school_id=school.id, score=7.0, max_score=10.0,
        review_status="pending",
    )
    db.add(ai_result)
    await db.commit()

    # AI 给 7 分，StudentAnswer.score=2，无 TeacherReview → 有效分 = 7（AI 分数）
    score = await _get_effective_score(db, answer_id=sa.id)
    assert score == 7.0


@pytest.mark.asyncio
async def test_effective_score_student_answer_only(db):
    """TG-004: _get_effective_score 分支 3 — 仅 StudentAnswer.score（无 AI）。"""
    school = School(name="测试", code="DP04")
    db.add(school)
    await db.flush()
    exam = Exam(name="考试", card_title="考试", school_id=school.id, status="completed")
    db.add(exam)
    await db.flush()
    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()
    q = Question(subject_id=subj.id, school_id=school.id, name="1", question_type="objective", max_score=5)
    db.add(q)
    await db.flush()

    sa = StudentAnswer(
        exam_id=exam.id, subject_id=subj.id, student_id="stu_obj",
        question_id=q.id, school_id=school.id, score=5.0,
    )
    db.add(sa)
    await db.commit()

    # 选择题：只有 StudentAnswer.score，无 AIGradingResult → 有效分 = 5
    score = await _get_effective_score(db, answer_id=sa.id)
    assert score == 5.0


@pytest.mark.asyncio
async def test_effective_score_nonexistent(db):
    """TG-004: _get_effective_score 不存在的 answer 返回 None。"""
    score = await _get_effective_score(db, answer_id="nonexistent-id")
    assert score is None


@pytest.mark.asyncio
async def test_pipeline_empty_exam(db):
    """TG-004: 空考试（无答题）pipeline 返回 0。"""
    school = School(name="测试", code="DP05")
    db.add(school)
    await db.flush()
    exam = Exam(name="空考试", card_title="空", school_id=school.id, status="completed")
    db.add(exam)
    await db.flush()
    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()
    q = Question(subject_id=subj.id, school_id=school.id, name="1", question_type="objective", max_score=5)
    db.add(q)
    await db.commit()

    created_bank = await populate_bank_questions(db, exam_id=exam.id, school_id=school.id)
    assert created_bank == 1  # 题目存在但无答题

    # 验证空答案集的统计
    result = await db.execute(select(BankQuestion).where(BankQuestion.school_id == school.id))
    bq = result.scalars().first()
    assert bq.sample_count == 0
    assert bq.difficulty is None
    assert bq.discrimination is None

    created_errors = await populate_error_books(db, exam_id=exam.id, school_id=school.id)
    assert created_errors == 0  # 无答题 → 无错题


@pytest.mark.asyncio
async def test_no_subjects_returns_zero(db):
    """TG-004: 考试无科目时 populate_bank_questions 返回 0。"""
    school = School(name="测试", code="DP06")
    db.add(school)
    await db.flush()
    exam = Exam(name="空考试", card_title="空", school_id=school.id, status="completed")
    db.add(exam)
    await db.commit()

    created = await populate_bank_questions(db, exam_id=exam.id, school_id=school.id)
    assert created == 0


@pytest.mark.asyncio
async def test_discrimination_with_10_samples(db):
    """R2-004: >=10 样本时 discrimination 被计算且精确。"""
    school = School(name="测试", code="DP07")
    db.add(school)
    await db.flush()
    exam = Exam(name="考试", card_title="考试", school_id=school.id, status="completed")
    db.add(exam)
    await db.flush()
    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()
    q = Question(subject_id=subj.id, school_id=school.id, name="1", question_type="objective", max_score=10)
    db.add(q)
    await db.flush()

    # 10 个学生，分数从 1 到 10
    scores = [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
    for i, s in enumerate(scores):
        sa = StudentAnswer(
            exam_id=exam.id, subject_id=subj.id, student_id=f"disc_stu{i:03d}",
            question_id=q.id, school_id=school.id, score=float(s),
        )
        db.add(sa)
    await db.commit()

    created = await populate_bank_questions(db, exam_id=exam.id, school_id=school.id)
    assert created == 1

    result = await db.execute(select(BankQuestion).where(BankQuestion.school_id == school.id))
    bq = result.scalars().first()
    assert bq.sample_count == 10
    assert bq.discrimination is not None

    # 手动计算: n27 = max(1, int(10 * 0.27)) = 2
    # high_group = [10, 9] → avg rate = 19/(2*10) = 0.95
    # low_group = [2, 1] → avg rate = 3/(2*10) = 0.15
    # discrimination = 0.95 - 0.15 = 0.80
    assert bq.discrimination == pytest.approx(0.80, abs=0.01)

    # difficulty = sum(1..10)/(10*10) = 55/100 = 0.55
    assert bq.difficulty == pytest.approx(0.55, abs=0.01)
