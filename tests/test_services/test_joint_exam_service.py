import pytest
from edu_cloud.services.joint_exam_service import JointExamService
from edu_cloud.services.school_service import SchoolService
from edu_cloud.services.exceptions import NotFoundError, StateError, ConflictError, ValidationError
from edu_cloud.models.platform_user import PlatformUser


@pytest.fixture
async def setup(db):
    """Create user + 2 schools for testing."""
    user = PlatformUser(username="coord", display_name="C", role="exam_coordinator")
    user.set_password("test")
    db.add(user)
    await db.commit()

    svc = SchoolService(db)
    s1, _ = await svc.create_school("出题校", "CREATOR01", "区1")
    s2, _ = await svc.create_school("参与校", "PART01", "区1")
    return {"user": user, "s1": s1, "s2": s2, "db": db}


@pytest.mark.asyncio
async def test_create_exam_with_creator(setup):
    d = setup
    svc = JointExamService(d["db"])
    exam = await svc.create_exam(
        name="春季联考",
        subjects=[{"code": "YW", "name": "语文", "max_score": 150}],
        creator_school_id=d["s1"].id,
        created_by=d["user"].id,
    )
    assert exam.status == "draft"
    assert exam.creator_school_id == d["s1"].id
    # Creator auto-added as participant
    detail = await svc.get_exam_detail(exam.id)
    creators = [p for p in detail["participants"] if p["is_creator"]]
    assert len(creators) == 1


@pytest.mark.asyncio
async def test_add_remove_participant(setup):
    d = setup
    svc = JointExamService(d["db"])
    exam = await svc.create_exam(
        name="E", subjects=[], creator_school_id=d["s1"].id, created_by=d["user"].id,
    )
    # Add participant
    p = await svc.add_participant(exam.id, d["s2"].id)
    assert p.school_id == d["s2"].id
    assert p.is_creator is False

    # Remove
    await svc.remove_participant(exam.id, d["s2"].id)
    detail = await svc.get_exam_detail(exam.id)
    assert len(detail["participants"]) == 1  # only creator left


@pytest.mark.asyncio
async def test_distribute_requires_templates_ready(setup):
    d = setup
    svc = JointExamService(d["db"])
    exam = await svc.create_exam(
        name="E", subjects=[{"code": "YW", "name": "语文", "max_score": 150}],
        creator_school_id=d["s1"].id, created_by=d["user"].id,
    )
    with pytest.raises(StateError, match="templates_ready"):
        await svc.distribute(exam.id)


@pytest.mark.asyncio
async def test_remove_creator_fails(setup):
    d = setup
    svc = JointExamService(d["db"])
    exam = await svc.create_exam(
        name="E", subjects=[], creator_school_id=d["s1"].id, created_by=d["user"].id,
    )
    with pytest.raises(ValidationError):
        await svc.remove_participant(exam.id, d["s1"].id)


@pytest.mark.asyncio
async def test_add_duplicate_participant_fails(setup):
    d = setup
    svc = JointExamService(d["db"])
    exam = await svc.create_exam(
        name="E", subjects=[], creator_school_id=d["s1"].id, created_by=d["user"].id,
    )
    await svc.add_participant(exam.id, d["s2"].id)
    with pytest.raises(ConflictError):
        await svc.add_participant(exam.id, d["s2"].id)


# --- Task 7: 模板上传 + 成绩提交 + 状态推进 ---


@pytest.mark.asyncio
async def test_upload_template_auto_promotes(setup, tmp_path):
    d = setup
    svc = JointExamService(d["db"], upload_dir=str(tmp_path))
    exam = await svc.create_exam(
        name="E",
        subjects=[{"code": "YW", "name": "语文", "max_score": 150}],
        creator_school_id=d["s1"].id,
        created_by=d["user"].id,
    )
    assert exam.status == "draft"

    await svc.upload_template(
        exam_id=exam.id,
        subject_code="YW",
        skeleton_data={"regions": []},
        pdf_bytes=b"%PDF-fake",
        answer_schema=[{"id": "q1", "max_score": 10, "type": "主观题"}],
    )
    await d["db"].refresh(exam)
    assert exam.status == "templates_ready"  # auto-promoted (only 1 subject)
    assert exam.answer_detail_schema["YW"][0]["id"] == "q1"


@pytest.mark.asyncio
async def test_submit_scores_full_cycle(setup, tmp_path):
    d = setup
    svc = JointExamService(d["db"], upload_dir=str(tmp_path))
    exam = await svc.create_exam(
        name="E",
        subjects=[{"code": "YW", "name": "语文", "max_score": 150}],
        creator_school_id=d["s1"].id,
        created_by=d["user"].id,
    )
    # Upload template → promote → distribute
    await svc.upload_template(exam.id, "YW", {}, b"pdf", [{"id": "q1", "max_score": 10}])
    await svc.distribute(exam.id)
    assert exam.status == "distributed"

    # Submit scores from creator school
    await svc.submit_scores(exam.id, d["s1"].id, "YW", [
        {"student_name": "张三", "student_number": "001", "total_score": 85,
         "detail_scores": [{"question_id": "q1", "score": 8, "max_score": 10}]},
    ])
    await d["db"].refresh(exam)
    assert exam.status == "completed"  # only 1 participant (creator), 1 subject → auto-complete


@pytest.mark.asyncio
async def test_submit_scores_upsert(setup, tmp_path):
    d = setup
    svc = JointExamService(d["db"], upload_dir=str(tmp_path))
    exam = await svc.create_exam(
        name="E", subjects=[{"code": "YW", "name": "语文", "max_score": 150}],
        creator_school_id=d["s1"].id, created_by=d["user"].id,
    )
    # Add s2 so auto-complete doesn't trigger on first submission
    await svc.add_participant(exam.id, d["s2"].id)
    await svc.upload_template(exam.id, "YW", {}, b"pdf", [])
    await svc.distribute(exam.id)

    # First submission
    await svc.submit_scores(exam.id, d["s1"].id, "YW", [
        {"student_name": "张三", "student_number": "001", "total_score": 80,
         "detail_scores": []},
    ])
    # Second submission (upsert — same student, updated score)
    await svc.submit_scores(exam.id, d["s1"].id, "YW", [
        {"student_name": "张三", "student_number": "001", "total_score": 90,
         "detail_scores": []},
    ])
    # Should have 1 record, not 2
    from sqlalchemy import select, func
    from edu_cloud.models.joint_exam import JointExamStudentResult
    count = (await d["db"].execute(
        select(func.count()).select_from(JointExamStudentResult)
    )).scalar()
    assert count == 1


@pytest.mark.asyncio
async def test_force_complete(setup, tmp_path):
    d = setup
    svc = JointExamService(d["db"], upload_dir=str(tmp_path))
    exam = await svc.create_exam(
        name="E", subjects=[{"code": "YW", "name": "语文", "max_score": 150}],
        creator_school_id=d["s1"].id, created_by=d["user"].id,
    )
    await svc.upload_template(exam.id, "YW", {}, b"pdf", [])
    await svc.distribute(exam.id)

    result = await svc.force_complete(exam.id)
    assert result.status == "completed"
