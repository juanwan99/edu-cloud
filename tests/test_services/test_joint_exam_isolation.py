"""联考管理跨校隔离测试。"""
import pytest
from edu_cloud.modules.exam.joint_exam_service import JointExamService
from edu_cloud.modules.exam.models import JointExam, JointExamParticipant


@pytest.fixture
async def joint_exam_with_participants(db):
    """Create a joint exam with two participant schools."""
    exam = JointExam(
        id="je-part", name="参与校测试", created_by="u", status="active",
        subjects=[], creator_school_id="school-a",
    )
    db.add(exam)
    await db.flush()
    db.add(JointExamParticipant(
        joint_exam_id="je-part", school_id="school-a", status="active", is_creator=True,
    ))
    db.add(JointExamParticipant(
        joint_exam_id="je-part", school_id="school-b", status="active", is_creator=False,
    ))
    await db.commit()
    return exam


@pytest.mark.asyncio
async def test_list_exams_filtered_by_participant(db, joint_exam_with_participants):
    """Participant school sees only exams it participates in."""
    svc = JointExamService(db)
    exams_a = await svc.list_exams(school_id="school-a")
    assert len(exams_a) == 1
    assert exams_a[0].id == "je-part"

    exams_b = await svc.list_exams(school_id="school-b")
    assert len(exams_b) == 1

    exams_c = await svc.list_exams(school_id="school-c")
    assert len(exams_c) == 0


@pytest.mark.asyncio
async def test_list_exams_admin_sees_all(db, joint_exam_with_participants):
    """Admin (school_id=None) sees all exams."""
    svc = JointExamService(db)
    exams = await svc.list_exams(school_id=None)
    assert len(exams) == 1


@pytest.mark.asyncio
async def test_list_exams_combined_status_and_school_filter(db):
    """Status + school_id filters work together."""
    # Create two exams: one draft (school-x participant), one active (school-y participant)
    exam_draft = JointExam(
        id="je-draft", name="Draft Exam", created_by="u", status="draft",
        subjects=[], creator_school_id="school-x",
    )
    exam_active = JointExam(
        id="je-active", name="Active Exam", created_by="u", status="active",
        subjects=[], creator_school_id="school-y",
    )
    db.add_all([exam_draft, exam_active])
    await db.flush()
    db.add(JointExamParticipant(
        joint_exam_id="je-draft", school_id="school-x", status="active", is_creator=True,
    ))
    db.add(JointExamParticipant(
        joint_exam_id="je-active", school_id="school-y", status="active", is_creator=True,
    ))
    # school-x also participates in the active exam
    db.add(JointExamParticipant(
        joint_exam_id="je-active", school_id="school-x", status="active", is_creator=False,
    ))
    await db.commit()

    svc = JointExamService(db)

    # school-x sees both exams (participant in both)
    all_x = await svc.list_exams(school_id="school-x")
    assert len(all_x) == 2

    # school-x + status=draft sees only the draft
    draft_x = await svc.list_exams(status="draft", school_id="school-x")
    assert len(draft_x) == 1
    assert draft_x[0].id == "je-draft"

    # school-y sees only the active exam
    all_y = await svc.list_exams(school_id="school-y")
    assert len(all_y) == 1
    assert all_y[0].id == "je-active"
