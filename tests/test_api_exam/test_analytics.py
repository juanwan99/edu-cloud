import pytest
from sqlalchemy import select
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingTask, AIGradingResult
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def analytics_setup(client, db):
    school = School(name="AN", code="AN01")
    db.add(school)
    await db.commit()
    user = User(username="t", display_name="T")
    user.set_password("p")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="admin", school_id=school.id, is_primary=True))
    await db.flush()
    token = create_access_token({"sub": user.id, "school_id": school.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    exam = Exam(name="期中", school_id=school.id)
    db.add(exam)
    await db.commit()

    subject = Subject(exam_id=exam.id, name="语文", code="chinese", school_id=school.id)
    db.add(subject)
    await db.commit()

    q1 = Question(subject_id=subject.id, name="Q1", question_type="subjective", max_score=10.0, school_id=school.id)
    q2 = Question(subject_id=subject.id, name="Q2", question_type="subjective", max_score=10.0, school_id=school.id)
    db.add_all([q1, q2])
    await db.commit()

    task = GradingTask(
        subject_id=subject.id, school_id=school.id,
        status="completed", total=6, completed=6, failed=0, created_by=user.id,
    )
    db.add(task)
    await db.commit()

    # 3 students, 2 questions each
    for sid, scores in [("s1", [8, 7]), ("s2", [6, 9]), ("s3", [10, 5])]:
        for q, score in zip([q1, q2], scores):
            a = StudentAnswer(
                exam_id=exam.id, subject_id=subject.id, student_id=sid,
                question_id=q.id, image_path=f"/fake/{sid}_{q.id}.png", school_id=school.id,
            )
            db.add(a)
            await db.commit()
            r = AIGradingResult(
                task_id=task.id, answer_id=a.id, question_id=q.id,
                school_id=school.id, score=float(score), max_score=10.0,
                feedback="f", confidence=0.9, review_status="pending",
            )
            db.add(r)
            await db.commit()

    return {
        "headers": headers, "exam_id": exam.id, "subject_id": subject.id,
        "school_id": school.id,
    }


async def test_exam_summary(client, analytics_setup):
    resp = await client.get(
        f"/api/v1/analytics/exam/{analytics_setup['exam_id']}/summary",
        headers=analytics_setup["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_students"] == 3
    assert len(data["subjects"]) == 1
    subj = data["subjects"][0]
    assert subj["subject_name"] == "语文"
    # s1: 8+7=15, s2: 6+9=15, s3: 10+5=15 → avg=15, max=15, min=15
    assert subj["avg_score"] == 15.0
    assert subj["highest"] == 15.0
    assert subj["lowest"] == 15.0
    assert subj["max_score_possible"] == 20.0
    assert subj["score_rate"] == 0.75
    assert subj["graded_count"] == 3


async def test_exam_summary_not_found(client, analytics_setup):
    resp = await client.get(
        "/api/v1/analytics/exam/nonexistent/summary",
        headers=analytics_setup["headers"],
    )
    assert resp.status_code == 404


async def test_exam_summary_cross_tenant(client, analytics_setup, db):
    other_school = School(name="Other", code="OT01")
    db.add(other_school)
    await db.commit()
    other_user = User(username="x", display_name="X")
    other_user.set_password("p")
    db.add(other_user)
    await db.commit()
    db.add(UserRole(user_id=other_user.id, role="teacher", school_id=other_school.id, is_primary=True))
    await db.flush()
    token = create_access_token({"sub": other_user.id, "school_id": other_school.id, "role": "teacher"})
    other_headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get(
        f"/api/v1/analytics/exam/{analytics_setup['exam_id']}/summary",
        headers=other_headers,
    )
    assert resp.status_code == 404


async def test_exam_summary_no_grading_data(client, db, analytics_setup):
    """考试下有 subject 但无批改数据时应返回 null 统计"""
    subject2 = Subject(
        exam_id=analytics_setup["exam_id"], name="数学", code="math",
        school_id=analytics_setup["school_id"],
    )
    db.add(subject2)
    await db.commit()
    q = Question(
        subject_id=subject2.id, name="MQ1", question_type="subjective",
        max_score=10.0, school_id=analytics_setup["school_id"],
    )
    db.add(q)
    await db.commit()

    resp = await client.get(
        f"/api/v1/analytics/exam/{analytics_setup['exam_id']}/summary",
        headers=analytics_setup["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    # 总学生数仍为 3（来自语文科目）
    assert data["total_students"] == 3
    assert len(data["subjects"]) == 2
    # 数学科目无批改数据
    math_subj = next(s for s in data["subjects"] if s["subject_name"] == "数学")
    assert math_subj["avg_score"] is None
    assert math_subj["highest"] is None
    assert math_subj["lowest"] is None
    assert math_subj["score_rate"] is None
    assert math_subj["graded_count"] == 0


async def test_exam_summary_multiple_subjects(client, db, analytics_setup):
    """多科目场景：total_students 应为跨科目学生并集"""
    subject2 = Subject(
        exam_id=analytics_setup["exam_id"], name="数学2", code="math2",
        school_id=analytics_setup["school_id"],
    )
    db.add(subject2)
    await db.commit()
    q = Question(
        subject_id=subject2.id, name="MQ1", question_type="subjective",
        max_score=10.0, school_id=analytics_setup["school_id"],
    )
    db.add(q)
    await db.commit()

    task = GradingTask(
        subject_id=subject2.id, school_id=analytics_setup["school_id"],
        status="completed", total=2, completed=2, failed=0, created_by=(
            await db.execute(select(User).limit(1))
        ).scalar_one().id,
    )
    db.add(task)
    await db.commit()

    for sid, score in [("s1", 8.0), ("s4", 5.0)]:
        a = StudentAnswer(
            exam_id=analytics_setup["exam_id"], subject_id=subject2.id,
            student_id=sid, question_id=q.id,
            image_path=f"/fake/{sid}_math.png", school_id=analytics_setup["school_id"],
        )
        db.add(a)
        await db.commit()
        r = AIGradingResult(
            task_id=task.id, answer_id=a.id, question_id=q.id,
            school_id=analytics_setup["school_id"], score=score, max_score=10.0,
            feedback="f", confidence=0.9, review_status="pending",
        )
        db.add(r)
        await db.commit()

    resp = await client.get(
        f"/api/v1/analytics/exam/{analytics_setup['exam_id']}/summary",
        headers=analytics_setup["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    # s1, s2, s3 from 语文 + s4 from 数学2 = 4 unique students
    assert data["total_students"] == 4


async def test_distribution_all_subjects(client, analytics_setup):
    resp = await client.get(
        f"/api/v1/analytics/exam/{analytics_setup['exam_id']}/distribution",
        headers=analytics_setup["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_students"] == 3
    assert "intervals" in data
    # All students scored 15/20 = 75%, falls in 70-79 range
    total_in_intervals = sum(i["count"] for i in data["intervals"])
    assert total_in_intervals == 3


async def test_distribution_by_subject(client, analytics_setup):
    resp = await client.get(
        f"/api/v1/analytics/exam/{analytics_setup['exam_id']}/distribution?subject_id={analytics_setup['subject_id']}",
        headers=analytics_setup["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["subject_id"] == analytics_setup["subject_id"]
    assert data["total_students"] == 3


async def test_subject_questions_analysis(client, analytics_setup):
    resp = await client.get(
        f"/api/v1/analytics/subject/{analytics_setup['subject_id']}/questions",
        headers=analytics_setup["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["subject_name"] == "语文"
    assert len(data["questions"]) == 2
    for q in data["questions"]:
        assert "avg_score" in q
        assert "score_rate" in q
        assert "graded_count" in q
        assert q["graded_count"] == 3
        assert q["max_score"] == 10.0


async def test_subject_questions_not_found(client, analytics_setup):
    resp = await client.get(
        "/api/v1/analytics/subject/nonexistent/questions",
        headers=analytics_setup["headers"],
    )
    assert resp.status_code == 404
