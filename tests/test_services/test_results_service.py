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
async def test_rankings_all_subjects(db):
    """全科总分排名需要跨科汇总：构造单科第一 ≠ 总分第一的数据。"""
    exam = JointExam(
        name="多科联考", created_by="u", status="completed",
        subjects=[{"code": "YW", "name": "语文", "max_score": 150},
                  {"code": "SX", "name": "数学", "max_score": 150}],
    )
    db.add(exam)
    await db.commit()

    # 张三: 语文95(单科第一) + 数学50 = 总分145
    # 李四: 语文80 + 数学90 = 总分170(总分第一)
    for name, num, yw, sx in [("张三", "001", 95, 50), ("李四", "002", 80, 90)]:
        for subj, score in [("YW", yw), ("SX", sx)]:
            db.add(JointExamStudentResult(
                joint_exam_id=exam.id, school_id="s1", subject_code=subj,
                student_name=name, student_number=num, total_score=float(score),
                detail_scores=[],
            ))
    await db.commit()

    svc = ResultsService(db)
    rankings = await svc.get_rankings(exam.id, subject_code=None)
    assert len(rankings) == 2
    # 总分第一应该是李四(170)，不是语文单科第一张三(95)
    assert rankings[0]["student_name"] == "李四"
    assert rankings[0]["total_score"] == 170.0
    assert rankings[1]["student_name"] == "张三"
    assert rankings[1]["total_score"] == 145.0


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
async def test_student_detail_cross_school_disambiguation(db):
    """跨校学号重复时，school_id 参数正确隔离。"""
    exam = JointExam(
        name="重号测试", created_by="u", status="completed",
        subjects=[{"code": "YW", "name": "语文", "max_score": 150}],
    )
    db.add(exam)
    await db.commit()
    # 两校同学号 001
    db.add(JointExamStudentResult(
        joint_exam_id=exam.id, school_id="s1", subject_code="YW",
        student_name="张三", student_number="001", total_score=90.0, detail_scores=[],
    ))
    db.add(JointExamStudentResult(
        joint_exam_id=exam.id, school_id="s2", subject_code="YW",
        student_name="李四", student_number="001", total_score=80.0, detail_scores=[],
    ))
    await db.commit()

    svc = ResultsService(db)
    # 不带 school_id → 两条记录都返回（允许但可能混淆）
    detail_all = await svc.get_student_detail(exam.id, "001")
    assert len(detail_all["subjects"]) == 2

    # 带 school_id → 只返回该校学生
    detail_s1 = await svc.get_student_detail(exam.id, "001", school_id="s1")
    assert detail_s1["student_name"] == "张三"
    assert len(detail_s1["subjects"]) == 1
    assert detail_s1["school_id"] == "s1"

    detail_s2 = await svc.get_student_detail(exam.id, "001", school_id="s2")
    assert detail_s2["student_name"] == "李四"
    assert detail_s2["school_id"] == "s2"


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
