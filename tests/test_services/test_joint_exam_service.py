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
