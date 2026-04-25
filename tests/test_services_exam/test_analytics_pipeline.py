"""Tests for analytics pipeline_service — compute_exam_analysis fills 3 tables."""
import pytest
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingTask, GradingResult
from edu_cloud.modules.knowledge.models import KnowledgePoint, QuestionKnowledgePoint
from edu_cloud.modules.analytics.models import ClassAnalysis, StudentAnalysis, StudentKnpMastery


@pytest.fixture
async def pipeline_data(db: AsyncSession):
    """Two classes, 4 students, 1 exam with 2 subjects (3 questions each), knowledge points."""
    school = School(name="Pipeline School", code="PS01")
    db.add(school)
    await db.flush()

    user = User(username="pipe_admin", display_name="Admin")
    user.set_password("p")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="admin", school_id=school.id, is_primary=True))

    cls_a = Class(name="高一1班", grade="高一", school_id=school.id)
    cls_b = Class(name="高一2班", grade="高一", school_id=school.id)
    db.add_all([cls_a, cls_b])
    await db.flush()

    s1 = Student(name="张三", student_number="001", class_id=cls_a.id, school_id=school.id)
    s2 = Student(name="李四", student_number="002", class_id=cls_a.id, school_id=school.id)
    s3 = Student(name="王五", student_number="003", class_id=cls_b.id, school_id=school.id)
    s4 = Student(name="赵六", student_number="004", class_id=cls_b.id, school_id=school.id)
    db.add_all([s1, s2, s3, s4])
    await db.flush()

    exam = Exam(name="期中考试", school_id=school.id)
    db.add(exam)
    await db.flush()

    subj_math = Subject(exam_id=exam.id, name="数学", code="math", school_id=school.id)
    subj_chi = Subject(exam_id=exam.id, name="语文", code="chinese", school_id=school.id)
    db.add_all([subj_math, subj_chi])
    await db.flush()

    # Math: 3 questions, max_score 40+30+30=100
    mq1 = Question(subject_id=subj_math.id, name="M1", question_type="choice", max_score=40.0, school_id=school.id)
    mq2 = Question(subject_id=subj_math.id, name="M2", question_type="essay", max_score=30.0, school_id=school.id)
    mq3 = Question(subject_id=subj_math.id, name="M3", question_type="essay", max_score=30.0, school_id=school.id)
    # Chinese: 2 questions, max_score 50+50=100
    cq1 = Question(subject_id=subj_chi.id, name="C1", question_type="choice", max_score=50.0, school_id=school.id)
    cq2 = Question(subject_id=subj_chi.id, name="C2", question_type="essay", max_score=50.0, school_id=school.id)
    db.add_all([mq1, mq2, mq3, cq1, cq2])
    await db.flush()

    # Knowledge points (linked to math questions)
    kp_algebra = KnowledgePoint(code="ALG", name="代数", school_id=school.id)
    kp_geom = KnowledgePoint(code="GEO", name="几何", school_id=school.id)
    db.add_all([kp_algebra, kp_geom])
    await db.flush()
    # M1, M2 → algebra; M3 → geometry
    db.add_all([
        QuestionKnowledgePoint(question_id=mq1.id, knowledge_point_id=kp_algebra.id),
        QuestionKnowledgePoint(question_id=mq2.id, knowledge_point_id=kp_algebra.id),
        QuestionKnowledgePoint(question_id=mq3.id, knowledge_point_id=kp_geom.id),
    ])

    task = GradingTask(
        subject_id=subj_math.id, school_id=school.id,
        status="completed", total=12, completed=12, failed=0, created_by=user.id,
    )
    db.add(task)
    await db.flush()

    # Scores layout (math, full=100):
    #   s1: M1=36, M2=24, M3=27 → total=87 (pass+excellent)
    #   s2: M1=28, M2=18, M3=15 → total=61 (pass only)
    #   s3: M1=40, M2=30, M3=28 → total=98 (pass+excellent)
    #   s4: M1=20, M2=10, M3=12 → total=42 (fail)
    math_scores = {
        s1.id: [(mq1, 36), (mq2, 24), (mq3, 27)],
        s2.id: [(mq1, 28), (mq2, 18), (mq3, 15)],
        s3.id: [(mq1, 40), (mq2, 30), (mq3, 28)],
        s4.id: [(mq1, 20), (mq2, 10), (mq3, 12)],
    }
    # Chinese scores (full=100):
    #   s1: C1=45, C2=40 → total=85 (pass+excellent)
    #   s2: C1=30, C2=25 → total=55 (fail)
    #   s3: C1=48, C2=42 → total=90 (pass+excellent)
    #   s4: C1=35, C2=30 → total=65 (pass only)
    chi_scores = {
        s1.id: [(cq1, 45), (cq2, 40)],
        s2.id: [(cq1, 30), (cq2, 25)],
        s3.id: [(cq1, 48), (cq2, 42)],
        s4.id: [(cq1, 35), (cq2, 30)],
    }

    for sid, items in math_scores.items():
        for q, score in items:
            a = StudentAnswer(
                exam_id=exam.id, subject_id=subj_math.id, student_id=sid,
                question_id=q.id, image_path=f"/fake/{sid}_{q.id}.png", school_id=school.id,
            )
            db.add(a)
            await db.flush()
            r = GradingResult(
                ai_task_id=task.id, answer_id=a.id, question_id=q.id,
                school_id=school.id, ai_score=float(score), final_score=float(score),
                max_score=q.max_score, ai_feedback="ok", ai_confidence=0.95, status="confirmed",
            )
            db.add(r)

    task2 = GradingTask(
        subject_id=subj_chi.id, school_id=school.id,
        status="completed", total=8, completed=8, failed=0, created_by=user.id,
    )
    db.add(task2)
    await db.flush()

    for sid, items in chi_scores.items():
        for q, score in items:
            a = StudentAnswer(
                exam_id=exam.id, subject_id=subj_chi.id, student_id=sid,
                question_id=q.id, image_path=f"/fake/{sid}_{q.id}.png", school_id=school.id,
            )
            db.add(a)
            await db.flush()
            r = GradingResult(
                ai_task_id=task2.id, answer_id=a.id, question_id=q.id,
                school_id=school.id, ai_score=float(score), final_score=float(score),
                max_score=q.max_score, ai_feedback="ok", ai_confidence=0.95, status="confirmed",
            )
            db.add(r)

    await db.commit()

    return {
        "school_id": school.id,
        "exam_id": exam.id,
        "subj_math_id": subj_math.id,
        "subj_chi_id": subj_chi.id,
        "cls_a_id": cls_a.id,
        "cls_b_id": cls_b.id,
        "s1_id": s1.id, "s2_id": s2.id, "s3_id": s3.id, "s4_id": s4.id,
        "kp_algebra_id": kp_algebra.id, "kp_geom_id": kp_geom.id,
    }


async def test_class_analysis_populated(db: AsyncSession, pipeline_data):
    """compute_exam_analysis should fill ClassAnalysis with correct stats per class×subject."""
    from edu_cloud.modules.analytics.pipeline_service import compute_exam_analysis

    await compute_exam_analysis(db, exam_id=pipeline_data["exam_id"], school_id=pipeline_data["school_id"])

    rows = (await db.execute(
        select(ClassAnalysis).where(ClassAnalysis.exam_id == pipeline_data["exam_id"])
    )).scalars().all()

    # 2 subjects × 2 classes = 4 rows
    assert len(rows) == 4

    # Math, class A (s1=87, s2=61): avg=74, pass_rate=100%, excellent_rate=50%
    ca_math_a = next(r for r in rows if r.subject_id == pipeline_data["subj_math_id"] and r.class_id == pipeline_data["cls_a_id"])
    assert float(ca_math_a.avg_score) == 74.0
    assert ca_math_a.max_score == 87.0
    assert ca_math_a.min_score == 61.0
    assert float(ca_math_a.pass_rate) == pytest.approx(100.0, abs=0.01)
    assert float(ca_math_a.excellent_rate) == pytest.approx(50.0, abs=0.01)
    assert ca_math_a.student_count == 2

    # Math, class B (s3=98, s4=42): avg=70, pass_rate=50%, excellent_rate=50%
    ca_math_b = next(r for r in rows if r.subject_id == pipeline_data["subj_math_id"] and r.class_id == pipeline_data["cls_b_id"])
    assert float(ca_math_b.avg_score) == 70.0
    assert float(ca_math_b.pass_rate) == pytest.approx(50.0, abs=0.01)
    assert float(ca_math_b.excellent_rate) == pytest.approx(50.0, abs=0.01)
    assert ca_math_b.student_count == 2


async def test_student_analysis_populated(db: AsyncSession, pipeline_data):
    """compute_exam_analysis should fill StudentAnalysis with total scores and ranks."""
    from edu_cloud.modules.analytics.pipeline_service import compute_exam_analysis

    await compute_exam_analysis(db, exam_id=pipeline_data["exam_id"], school_id=pipeline_data["school_id"])

    rows = (await db.execute(
        select(StudentAnalysis).where(StudentAnalysis.exam_id == pipeline_data["exam_id"])
    )).scalars().all()

    assert len(rows) == 4

    by_student = {r.student_id: r for r in rows}

    # Total scores: s1=87+85=172, s2=61+55=116, s3=98+90=188, s4=42+65=107
    assert float(by_student[pipeline_data["s1_id"]].total_score) == 172.0
    assert float(by_student[pipeline_data["s2_id"]].total_score) == 116.0
    assert float(by_student[pipeline_data["s3_id"]].total_score) == 188.0
    assert float(by_student[pipeline_data["s4_id"]].total_score) == 107.0

    # Grade ranks (同分同名次跳号): s3=1, s1=2, s2=3, s4=4
    assert by_student[pipeline_data["s3_id"]].rank_in_grade == 1
    assert by_student[pipeline_data["s1_id"]].rank_in_grade == 2
    assert by_student[pipeline_data["s2_id"]].rank_in_grade == 3
    assert by_student[pipeline_data["s4_id"]].rank_in_grade == 4

    # Class ranks: cls_a: s1=1, s2=2; cls_b: s3=1, s4=2
    assert by_student[pipeline_data["s1_id"]].rank_in_class == 1
    assert by_student[pipeline_data["s2_id"]].rank_in_class == 2
    assert by_student[pipeline_data["s3_id"]].rank_in_class == 1
    assert by_student[pipeline_data["s4_id"]].rank_in_class == 2

    # subject_scores JSON
    s1_scores = by_student[pipeline_data["s1_id"]].subject_scores
    assert s1_scores[pipeline_data["subj_math_id"]] == 87.0
    assert s1_scores[pipeline_data["subj_chi_id"]] == 85.0


async def test_student_knp_mastery_populated(db: AsyncSession, pipeline_data):
    """compute_exam_analysis should fill StudentKnpMastery for students with KP-linked questions."""
    from edu_cloud.modules.analytics.pipeline_service import compute_exam_analysis

    await compute_exam_analysis(db, exam_id=pipeline_data["exam_id"], school_id=pipeline_data["school_id"])

    rows = (await db.execute(
        select(StudentKnpMastery).where(StudentKnpMastery.exam_id == pipeline_data["exam_id"])
    )).scalars().all()

    # 4 students × 2 KPs (algebra, geometry) = 8 rows
    assert len(rows) == 8

    def find(student_id, knp_id):
        return next(r for r in rows if r.student_id == student_id and r.knp_id == knp_id)

    # s1 algebra: (M1=36/40 + M2=24/30) → (36+24)/(40+30) = 60/70 ≈ 0.857
    s1_alg = find(pipeline_data["s1_id"], pipeline_data["kp_algebra_id"])
    assert float(s1_alg.stu_rate) == pytest.approx(60 / 70, abs=0.002)

    # s1 geometry: M3=27/30 = 0.9
    s1_geo = find(pipeline_data["s1_id"], pipeline_data["kp_geom_id"])
    assert float(s1_geo.stu_rate) == pytest.approx(27 / 30, abs=0.002)

    # s4 algebra: (M1=20/40 + M2=10/30) = 30/70 ≈ 0.429
    s4_alg = find(pipeline_data["s4_id"], pipeline_data["kp_algebra_id"])
    assert float(s4_alg.stu_rate) == pytest.approx(30 / 70, abs=0.002)


async def test_class_analysis_score_distribution(db: AsyncSession, pipeline_data):
    """ClassAnalysis.score_distribution should be a 10-bucket histogram."""
    from edu_cloud.modules.analytics.pipeline_service import compute_exam_analysis

    await compute_exam_analysis(db, exam_id=pipeline_data["exam_id"], school_id=pipeline_data["school_id"])

    ca = (await db.execute(
        select(ClassAnalysis).where(
            ClassAnalysis.exam_id == pipeline_data["exam_id"],
            ClassAnalysis.subject_id == pipeline_data["subj_math_id"],
            ClassAnalysis.class_id == pipeline_data["cls_a_id"],
        )
    )).scalar_one()

    dist = ca.score_distribution
    assert isinstance(dist, list)
    assert len(dist) == 10
    assert sum(b["count"] for b in dist) == 2  # 2 students in class A


async def test_class_analysis_common_wrong_questions(db: AsyncSession, pipeline_data):
    """ClassAnalysis.common_wrong_questions should list questions sorted by error rate desc."""
    from edu_cloud.modules.analytics.pipeline_service import compute_exam_analysis

    await compute_exam_analysis(db, exam_id=pipeline_data["exam_id"], school_id=pipeline_data["school_id"])

    ca = (await db.execute(
        select(ClassAnalysis).where(
            ClassAnalysis.exam_id == pipeline_data["exam_id"],
            ClassAnalysis.subject_id == pipeline_data["subj_math_id"],
            ClassAnalysis.class_id == pipeline_data["cls_b_id"],
        )
    )).scalar_one()

    wrongs = ca.common_wrong_questions
    assert isinstance(wrongs, list)
    assert len(wrongs) > 0
    # Each entry should have question_id, question_name, error_rate, avg_score_rate
    first = wrongs[0]
    assert "question_id" in first
    assert "error_rate" in first


async def test_idempotent_rerun(db: AsyncSession, pipeline_data):
    """Running compute_exam_analysis twice should not duplicate rows (upsert)."""
    from edu_cloud.modules.analytics.pipeline_service import compute_exam_analysis

    await compute_exam_analysis(db, exam_id=pipeline_data["exam_id"], school_id=pipeline_data["school_id"])
    await compute_exam_analysis(db, exam_id=pipeline_data["exam_id"], school_id=pipeline_data["school_id"])

    ca_count = len((await db.execute(
        select(ClassAnalysis).where(ClassAnalysis.exam_id == pipeline_data["exam_id"])
    )).scalars().all())
    sa_count = len((await db.execute(
        select(StudentAnalysis).where(StudentAnalysis.exam_id == pipeline_data["exam_id"])
    )).scalars().all())

    assert ca_count == 4  # 2 subjects × 2 classes
    assert sa_count == 4  # 4 students


async def test_student_analysis_weak_knowledge(db: AsyncSession, pipeline_data):
    """weak_knowledge should list KPs with mastery < 0.6."""
    from edu_cloud.modules.analytics.pipeline_service import compute_exam_analysis

    await compute_exam_analysis(db, exam_id=pipeline_data["exam_id"], school_id=pipeline_data["school_id"])

    sa = (await db.execute(
        select(StudentAnalysis).where(
            StudentAnalysis.student_id == pipeline_data["s4_id"],
            StudentAnalysis.exam_id == pipeline_data["exam_id"],
        )
    )).scalar_one()

    # s4 algebra=30/70≈0.429 (<0.6), geometry=12/30=0.4 (<0.6) → both weak
    weak = sa.weak_knowledge
    assert isinstance(weak, list)
    assert len(weak) == 2
