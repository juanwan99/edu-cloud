"""B3: grade-aggregates 端点 TDD。"""
import pytest
import sqlalchemy
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.models.student import Class, Student
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingTask, GradingResult
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def agg_setup(client, db):
    """2 classes, 6 students each (> k=5), varied scores."""
    school = School(id="ag_s", name="AGG", code="AGG01")
    db.add(school)
    await db.commit()

    c1 = Class(id="ag_c1", name="1班", grade="高二", school_id="ag_s")
    c2 = Class(id="ag_c2", name="2班", grade="高二", school_id="ag_s")
    db.add_all([c1, c2])
    await db.commit()

    admin = User(id="ag_admin", username="agadmin", display_name="Admin")
    admin.set_password("p")
    db.add(admin)
    await db.commit()
    db.add(UserRole(user_id=admin.id, role="admin", school_id="ag_s", is_primary=True))
    await db.flush()

    exam = Exam(id="ag_exam", name="期中", school_id="ag_s")
    db.add(exam)
    await db.commit()
    subj = Subject(id="ag_subj", exam_id="ag_exam", name="语文", code="YW", school_id="ag_s")
    db.add(subj)
    await db.commit()
    q = Question(id="ag_q1", subject_id="ag_subj", name="Q1",
                 question_type="essay", max_score=100.0, school_id="ag_s")
    db.add(q)
    await db.commit()

    task = GradingTask(
        subject_id="ag_subj", school_id="ag_s",
        status="completed", total=12, completed=12, failed=0, created_by="ag_admin",
    )
    db.add(task)
    await db.commit()

    # c1: scores 80,85,90,75,70,88 → avg=81.33
    # c2: scores 60,65,70,55,72,68 → avg=65.0
    c1_scores = [80, 85, 90, 75, 70, 88]
    c2_scores = [60, 65, 70, 55, 72, 68]

    for i, score in enumerate(c1_scores):
        sid = f"ag_s1_{i}"
        st = Student(id=sid, name=f"c1学生{i}", student_number=f"AG1{i:03d}", class_id="ag_c1", school_id="ag_s")
        db.add(st)
        await db.commit()
        a = StudentAnswer(exam_id="ag_exam", subject_id="ag_subj", student_id=sid,
                          question_id="ag_q1", image_path=f"/fake/{sid}.png", school_id="ag_s")
        db.add(a)
        await db.commit()
        r = GradingResult(ai_task_id=task.id, answer_id=a.id, question_id="ag_q1",
                            school_id="ag_s", ai_score=float(score), final_score=float(score), max_score=100.0,
                            ai_feedback="f", ai_confidence=0.9, status="ai_done")
        db.add(r)
        await db.commit()

    for i, score in enumerate(c2_scores):
        sid = f"ag_s2_{i}"
        st = Student(id=sid, name=f"c2学生{i}", student_number=f"AG2{i:03d}", class_id="ag_c2", school_id="ag_s")
        db.add(st)
        await db.commit()
        a = StudentAnswer(exam_id="ag_exam", subject_id="ag_subj", student_id=sid,
                          question_id="ag_q1", image_path=f"/fake/{sid}.png", school_id="ag_s")
        db.add(a)
        await db.commit()
        r = GradingResult(ai_task_id=task.id, answer_id=a.id, question_id="ag_q1",
                            school_id="ag_s", ai_score=float(score), final_score=float(score), max_score=100.0,
                            ai_feedback="f", ai_confidence=0.9, status="ai_done")
        db.add(r)
        await db.commit()

    # head_teacher sees only c1
    teacher = User(id="ag_ht", username="aght", display_name="班主任")
    teacher.set_password("p")
    db.add(teacher)
    await db.commit()
    db.add(UserRole(user_id=teacher.id, role="head_teacher", school_id="ag_s", is_primary=True, class_ids=["ag_c1"]))
    await db.flush()

    admin_headers = {"Authorization": f"Bearer {create_access_token({'sub': 'ag_admin', 'school_id': 'ag_s', 'role': 'admin'})}"}
    teacher_headers = {"Authorization": f"Bearer {create_access_token({'sub': 'ag_ht', 'school_id': 'ag_s', 'role': 'head_teacher'})}"}
    return {"headers": admin_headers, "teacher_headers": teacher_headers}


async def test_grade_aggregates_basic(client, agg_setup):
    """Should return grade-level stats."""
    resp = await client.get(
        "/api/v1/analytics/exam/ag_exam/grade-aggregates?subject_id=ag_subj",
        headers=agg_setup["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["exam_id"] == "ag_exam"
    gs = data["grade_stats"]
    assert gs["student_count"] == 12
    assert gs["avg_score"] is not None
    assert gs["median_score"] is not None
    assert gs["p25"] is not None
    assert gs["p75"] is not None


async def test_class_ranking_order(client, agg_setup):
    """Classes should be ranked by avg_score descending."""
    resp = await client.get(
        "/api/v1/analytics/exam/ag_exam/grade-aggregates?subject_id=ag_subj",
        headers=agg_setup["headers"],
    )
    data = resp.json()
    rankings = data["class_rankings"]
    assert len(rankings) == 2
    assert rankings[0]["rank"] == 1
    assert rankings[1]["rank"] == 2
    # c1 avg > c2 avg
    assert rankings[0]["class_id"] == "ag_c1"
    assert rankings[1]["class_id"] == "ag_c2"


async def test_k_anonymity_suppression(client, db, agg_setup):
    """Class with < 5 students should have suppressed stats."""
    # Add a 3rd class with only 3 students
    c3 = Class(id="ag_c3", name="3班", grade="高二", school_id="ag_s")
    db.add(c3)
    await db.commit()

    import sqlalchemy
    task_result = await db.execute(
        sqlalchemy.select(GradingTask).where(GradingTask.school_id == "ag_s")
    )
    task = task_result.scalar_one()

    for i in range(3):  # only 3 students — below k=5
        sid = f"ag_s3_{i}"
        st = Student(id=sid, name=f"c3学生{i}", student_number=f"AG3{i:03d}", class_id="ag_c3", school_id="ag_s")
        db.add(st)
        await db.commit()
        a = StudentAnswer(exam_id="ag_exam", subject_id="ag_subj", student_id=sid,
                          question_id="ag_q1", image_path=f"/fake/{sid}.png", school_id="ag_s")
        db.add(a)
        await db.commit()
        r = GradingResult(ai_task_id=task.id, answer_id=a.id, question_id="ag_q1",
                            school_id="ag_s", ai_score=90.0, final_score=90.0, max_score=100.0,
                            ai_feedback="f", ai_confidence=0.9, status="ai_done")
        db.add(r)
        await db.commit()

    resp = await client.get(
        "/api/v1/analytics/exam/ag_exam/grade-aggregates?subject_id=ag_subj",
        headers=agg_setup["headers"],
    )
    data = resp.json()
    rankings = data["class_rankings"]
    c3_entry = next(r for r in rankings if r["class_id"] == "ag_c3")
    assert c3_entry["avg_score"] is None  # suppressed
    assert c3_entry["student_count"] == 3  # count is always visible


async def test_filter_by_subject(client, db, agg_setup):
    """When subject_id is specified, only that subject's scores are aggregated."""
    # Add a second subject with scores for a SUBSET of students (only c1, 6 students)
    subj2 = Subject(id="ag_subj2", exam_id="ag_exam", name="数学", code="SX", school_id="ag_s")
    db.add(subj2)
    await db.commit()
    q2 = Question(id="ag_q2", subject_id="ag_subj2", name="MQ1",
                  question_type="essay", max_score=100.0, school_id="ag_s")
    db.add(q2)
    await db.commit()

    task_result = await db.execute(
        sqlalchemy.select(GradingTask).where(GradingTask.school_id == "ag_s")
    )
    task = task_result.scalar_one()

    # Only c1 students have math scores — different student count from 语文 (12)
    for i in range(6):
        sid = f"ag_s1_{i}"  # reuse c1 students
        a = StudentAnswer(exam_id="ag_exam", subject_id="ag_subj2", student_id=sid,
                          question_id="ag_q2", image_path=f"/fake/{sid}_math.png", school_id="ag_s")
        db.add(a)
        await db.commit()
        db.add(GradingResult(ai_task_id=task.id, answer_id=a.id, question_id="ag_q2",
                               school_id="ag_s", ai_score=50.0, final_score=50.0, max_score=100.0,
                               ai_feedback="f", ai_confidence=0.9, status="ai_done"))
        await db.commit()

    # Query 语文 only → 12 students
    resp = await client.get(
        "/api/v1/analytics/exam/ag_exam/grade-aggregates?subject_id=ag_subj",
        headers=agg_setup["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["subject_id"] == "ag_subj"
    assert data["grade_stats"]["student_count"] == 12

    # Query 数学 only → 6 students (only c1)
    resp_math = await client.get(
        "/api/v1/analytics/exam/ag_exam/grade-aggregates?subject_id=ag_subj2",
        headers=agg_setup["headers"],
    )
    assert resp_math.status_code == 200
    math_data = resp_math.json()
    assert math_data["subject_id"] == "ag_subj2"
    assert math_data["grade_stats"]["student_count"] == 6

    # Query without subject_id → aggregates both subjects, still 12 students
    # (c1 students have both 语文+数学, c2 only has 语文)
    resp2 = await client.get(
        "/api/v1/analytics/exam/ag_exam/grade-aggregates",
        headers=agg_setup["headers"],
    )
    assert resp2.status_code == 200
    assert resp2.json()["subject_id"] is None
    assert resp2.json()["grade_stats"]["student_count"] == 12


async def test_grade_level_below_k_threshold(client, db, agg_setup):
    """When total students < k=5, grade_stats values should be null with note."""
    # Create a new exam with only 3 students total
    exam3 = Exam(id="ag_exam3", name="小考试", school_id="ag_s")
    db.add(exam3)
    await db.commit()
    subj3 = Subject(id="ag_subj3", exam_id="ag_exam3", name="英语", code="YY", school_id="ag_s")
    db.add(subj3)
    await db.commit()
    q3 = Question(id="ag_q3", subject_id="ag_subj3", name="EQ1",
                  question_type="essay", max_score=100.0, school_id="ag_s")
    db.add(q3)
    await db.commit()
    task = GradingTask(subject_id="ag_subj3", school_id="ag_s",
                       status="completed", total=3, completed=3, failed=0, created_by="ag_admin")
    db.add(task)
    await db.commit()
    c_small = Class(id="ag_c_small", name="小班", grade="高二", school_id="ag_s")
    db.add(c_small)
    await db.commit()
    for i in range(3):
        sid = f"ag_small_{i}"
        db.add(Student(id=sid, name=f"小{i}", student_number=f"SM{i:03d}",
                       class_id="ag_c_small", school_id="ag_s"))
        await db.commit()
        a = StudentAnswer(exam_id="ag_exam3", subject_id="ag_subj3", student_id=sid,
                          question_id="ag_q3", image_path=f"/fake/{sid}.png", school_id="ag_s")
        db.add(a)
        await db.commit()
        r = GradingResult(ai_task_id=task.id, answer_id=a.id, question_id="ag_q3",
                            school_id="ag_s", ai_score=80.0, final_score=80.0, max_score=100.0,
                            ai_feedback="f", ai_confidence=0.9, status="ai_done")
        db.add(r)
        await db.commit()

    resp = await client.get(
        "/api/v1/analytics/exam/ag_exam3/grade-aggregates?subject_id=ag_subj3",
        headers=agg_setup["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["grade_stats"]["student_count"] == 3
    assert data["grade_stats"]["avg_score"] is None  # below k threshold
    assert data["k_anonymity_note"] is not None


async def test_single_class_rank_is_one(client, agg_setup):
    """With only one class above k threshold, rank should be 1."""
    resp = await client.get(
        "/api/v1/analytics/exam/ag_exam/grade-aggregates?subject_id=ag_subj",
        headers=agg_setup["headers"],
    )
    data = resp.json()
    rankings = data["class_rankings"]
    # First ranked class should have rank=1
    assert rankings[0]["rank"] == 1
    # Verify rank is sequential
    ranks = [r["rank"] for r in rankings]
    assert ranks == list(range(1, len(ranks) + 1))


async def test_no_data_empty_response(client, db, agg_setup):
    """Exam with no grading data should return empty stats."""
    exam2 = Exam(id="ag_exam2", name="空考试", school_id="ag_s")
    db.add(exam2)
    await db.commit()
    subj2 = Subject(id="ag_subj_empty", exam_id="ag_exam2", name="数学", code="SX", school_id="ag_s")
    db.add(subj2)
    await db.commit()

    resp = await client.get(
        "/api/v1/analytics/exam/ag_exam2/grade-aggregates?subject_id=ag_subj_empty",
        headers=agg_setup["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["grade_stats"]["student_count"] == 0
    assert data["class_rankings"] == []


# --- P1-T6-01: k=5 阈值边界测试 ---

async def test_k_threshold_exactly_4_suppressed(client, db, agg_setup):
    """Class with exactly 4 students (< 5) should have suppressed avg_score."""
    c4 = Class(id="ag_c4", name="4班", grade="高二", school_id="ag_s")
    db.add(c4)
    await db.commit()

    task_result = await db.execute(
        sqlalchemy.select(GradingTask).where(GradingTask.school_id == "ag_s")
    )
    task = task_result.scalar_one()

    for i in range(4):
        sid = f"ag_s4_{i}"
        db.add(Student(id=sid, name=f"c4学生{i}", student_number=f"AG4{i:03d}",
                       class_id="ag_c4", school_id="ag_s"))
        await db.commit()
        a = StudentAnswer(exam_id="ag_exam", subject_id="ag_subj", student_id=sid,
                          question_id="ag_q1", image_path=f"/fake/{sid}.png", school_id="ag_s")
        db.add(a)
        await db.commit()
        db.add(GradingResult(ai_task_id=task.id, answer_id=a.id, question_id="ag_q1",
                               school_id="ag_s", ai_score=75.0, final_score=75.0, max_score=100.0,
                               ai_feedback="f", ai_confidence=0.9, status="ai_done"))
        await db.commit()

    resp = await client.get(
        "/api/v1/analytics/exam/ag_exam/grade-aggregates?subject_id=ag_subj",
        headers=agg_setup["headers"],
    )
    data = resp.json()
    c4_entry = next(r for r in data["class_rankings"] if r["class_id"] == "ag_c4")
    assert c4_entry["avg_score"] is None  # 4 < 5 → suppressed
    assert c4_entry["student_count"] == 4


async def test_k_threshold_exactly_5_visible(client, db, agg_setup):
    """Class with exactly 5 students (>= 5) should have visible avg_score."""
    c5 = Class(id="ag_c5", name="5班", grade="高二", school_id="ag_s")
    db.add(c5)
    await db.commit()

    task_result = await db.execute(
        sqlalchemy.select(GradingTask).where(GradingTask.school_id == "ag_s")
    )
    task = task_result.scalar_one()

    for i in range(5):
        sid = f"ag_s5_{i}"
        db.add(Student(id=sid, name=f"c5学生{i}", student_number=f"AG5{i:03d}",
                       class_id="ag_c5", school_id="ag_s"))
        await db.commit()
        a = StudentAnswer(exam_id="ag_exam", subject_id="ag_subj", student_id=sid,
                          question_id="ag_q1", image_path=f"/fake/{sid}.png", school_id="ag_s")
        db.add(a)
        await db.commit()
        db.add(GradingResult(ai_task_id=task.id, answer_id=a.id, question_id="ag_q1",
                               school_id="ag_s", ai_score=82.0, final_score=82.0, max_score=100.0,
                               ai_feedback="f", ai_confidence=0.9, status="ai_done"))
        await db.commit()

    resp = await client.get(
        "/api/v1/analytics/exam/ag_exam/grade-aggregates?subject_id=ag_subj",
        headers=agg_setup["headers"],
    )
    data = resp.json()
    c5_entry = next(r for r in data["class_rankings"] if r["class_id"] == "ag_c5")
    assert c5_entry["avg_score"] is not None  # 5 >= 5 → visible
    assert c5_entry["avg_score"] == 82.0
    assert c5_entry["student_count"] == 5


# --- P1-T6-02: teacher 角色 + my_class 断言 ---

async def test_teacher_sees_full_grade_stats_with_my_class(client, agg_setup):
    """Teacher should see full grade stats (not filtered), with my_class marked."""
    resp = await client.get(
        "/api/v1/analytics/exam/ag_exam/grade-aggregates?subject_id=ag_subj",
        headers=agg_setup["teacher_headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    # Grade stats based on ALL students (12), not just teacher's class
    assert data["grade_stats"]["student_count"] == 12
    # Both classes visible in rankings
    rankings = data["class_rankings"]
    assert len(rankings) == 2
    # Teacher's class (ag_c1) marked as my_class=true
    c1_entry = next(r for r in rankings if r["class_id"] == "ag_c1")
    assert c1_entry["my_class"] is True
    # Other class marked as my_class=false
    c2_entry = next(r for r in rankings if r["class_id"] == "ag_c2")
    assert c2_entry["my_class"] is False
