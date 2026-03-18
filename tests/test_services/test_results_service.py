import pytest
from edu_cloud.services.results_service import ResultsService
from edu_cloud.models.joint_exam import JointExam, JointExamStudentResult


@pytest.fixture
async def results_data(db):
    """Seed exam + 2 schools × 3 students × 1 subject."""
    exam = JointExam(
        name="排名测试联考", created_by="user-id", status="completed",
        subjects=[{"code": "YW", "name": "语文", "max_score": 150}],
    )
    db.add(exam)
    await db.commit()

    students = [
        # school_id, name, number, score
        ("s1", "张三", "001", 90.0),
        ("s1", "李四", "002", 85.0),
        ("s1", "王五", "003", 70.0),
        ("s2", "赵六", "004", 95.0),
        ("s2", "孙七", "005", 60.0),
        ("s2", "周八", "006", 80.0),
    ]
    for sid, name, num, score in students:
        db.add(JointExamStudentResult(
            joint_exam_id=exam.id, school_id=sid, subject_code="YW",
            student_name=name, student_number=num, total_score=score,
            detail_scores=[{"question_id": "q1", "score": score, "max_score": 150}],
        ))
    await db.commit()
    return exam


@pytest.mark.asyncio
async def test_rankings_by_subject(db, results_data):
    exam = results_data
    svc = ResultsService(db)
    rankings = await svc.get_rankings(exam.id, subject_code="YW")
    assert len(rankings) == 6
    # First place: 赵六 (95)
    assert rankings[0]["student_name"] == "赵六"
    assert rankings[0]["total_score"] == 95.0
    # Rank order is descending
    scores = [r["total_score"] for r in rankings]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_rankings_all_subjects(db, results_data):
    exam = results_data
    svc = ResultsService(db)
    # With only 1 subject, all-subjects ranking = single-subject ranking
    rankings = await svc.get_rankings(exam.id, subject_code=None)
    assert len(rankings) == 6
    assert rankings[0]["total_score"] == 95.0


@pytest.mark.asyncio
async def test_school_comparison(db, results_data):
    exam = results_data
    svc = ResultsService(db)
    comparison = await svc.get_school_comparison(exam.id)
    # 2 schools, each with 1 subject
    assert len(comparison) == 2
    for entry in comparison:
        assert "avg_score" in entry
        assert "max_score" in entry
        assert "median_score" in entry
        assert "student_count" in entry
    # s1: avg=(90+85+70)/3=81.67, s2: avg=(95+60+80)/3=78.33
    s1_entry = next(e for e in comparison if e["school_id"] == "s1")
    assert abs(s1_entry["avg_score"] - 81.67) < 0.1
    assert s1_entry["max_score"] == 90.0
    assert s1_entry["median_score"] == 85.0  # median of [70, 85, 90]


@pytest.mark.asyncio
async def test_student_detail(db, results_data):
    exam = results_data
    svc = ResultsService(db)
    detail = await svc.get_student_detail(exam.id, "001")  # 张三
    assert detail["student_name"] == "张三"
    assert len(detail["subjects"]) == 1
    assert detail["subjects"][0]["total_score"] == 90.0
    assert detail["subjects"][0]["detail_scores"][0]["question_id"] == "q1"


@pytest.mark.asyncio
async def test_rankings_empty_exam(db):
    """无成绩数据的联考返回空列表。"""
    exam = JointExam(
        name="空联考", created_by="u", status="completed", subjects=[],
    )
    db.add(exam)
    await db.commit()
    svc = ResultsService(db)
    rankings = await svc.get_rankings(exam.id)
    assert rankings == []
