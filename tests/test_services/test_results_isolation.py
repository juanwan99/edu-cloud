"""联考成绩跨校隔离测试。"""
import pytest
from edu_cloud.services.results_service import ResultsService
from edu_cloud.models.joint_exam import JointExam, JointExamParticipant, JointExamStudentResult


@pytest.fixture
async def joint_exam_two_schools(db):
    """Seed exam with 2 schools, each with 2 students, 1 subject."""
    exam = JointExam(
        id="je-iso", name="隔离测试联考", created_by="u", status="completed",
        subjects=[{"code": "YW", "name": "语文", "max_score": 150}],
        creator_school_id="school-a",
    )
    db.add(exam)
    await db.flush()
    for sid in ("school-a", "school-b"):
        db.add(JointExamParticipant(
            joint_exam_id="je-iso", school_id=sid, status="completed",
            is_creator=(sid == "school-a"),
        ))
    students = [
        ("school-a", "张三", "001", 90.0),
        ("school-a", "李四", "002", 85.0),
        ("school-b", "王五", "003", 95.0),
        ("school-b", "赵六", "004", 70.0),
    ]
    for sid, name, num, score in students:
        db.add(JointExamStudentResult(
            joint_exam_id="je-iso", school_id=sid, subject_code="YW",
            student_name=name, student_number=num, total_score=score,
            detail_scores=[],
        ))
    await db.commit()
    return exam


@pytest.mark.asyncio
async def test_rankings_filtered_by_school(db, joint_exam_two_schools):
    """school_id filter returns only that school's students."""
    svc = ResultsService(db)
    rankings = await svc.get_rankings("je-iso", school_id="school-a", subject_code="YW")
    assert len(rankings) == 2
    school_ids = {r["school_id"] for r in rankings}
    assert school_ids == {"school-a"}


@pytest.mark.asyncio
async def test_rankings_admin_sees_all(db, joint_exam_two_schools):
    """school_id=None (platform_admin) returns all schools."""
    svc = ResultsService(db)
    rankings = await svc.get_rankings("je-iso", school_id=None, subject_code="YW")
    assert len(rankings) == 4


@pytest.mark.asyncio
async def test_rankings_all_subjects_filtered(db, joint_exam_two_schools):
    """All-subject total ranking also respects school_id filter."""
    svc = ResultsService(db)
    rankings = await svc.get_rankings("je-iso", school_id="school-b")
    assert len(rankings) == 2
    school_ids = {r["school_id"] for r in rankings}
    assert school_ids == {"school-b"}


@pytest.mark.asyncio
async def test_school_comparison_filtered(db, joint_exam_two_schools):
    """school_id filter returns only that school's comparison data."""
    svc = ResultsService(db)
    comparison = await svc.get_school_comparison("je-iso", school_id="school-a")
    school_ids = {r["school_id"] for r in comparison}
    assert school_ids == {"school-a"}


@pytest.mark.asyncio
async def test_school_comparison_admin_sees_all(db, joint_exam_two_schools):
    """school_id=None returns comparison for all schools."""
    svc = ResultsService(db)
    comparison = await svc.get_school_comparison("je-iso", school_id=None)
    school_ids = {r["school_id"] for r in comparison}
    assert school_ids == {"school-a", "school-b"}


@pytest.mark.asyncio
async def test_student_detail_rejects_other_school(db, joint_exam_two_schools):
    """Querying a student from another school raises NotFoundError."""
    svc = ResultsService(db)
    from edu_cloud.services.exceptions import NotFoundError
    # Student 003 belongs to school-b; querying with school-a should fail
    with pytest.raises(NotFoundError):
        await svc.get_student_detail("je-iso", "003", school_id="school-a")


@pytest.mark.asyncio
async def test_student_detail_same_school_succeeds(db, joint_exam_two_schools):
    """Querying a student from their own school succeeds."""
    svc = ResultsService(db)
    detail = await svc.get_student_detail("je-iso", "003", school_id="school-b")
    assert detail["student_name"] == "王五"
    assert detail["school_id"] == "school-b"
