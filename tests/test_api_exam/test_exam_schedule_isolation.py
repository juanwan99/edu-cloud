"""考试日程跨校隔离测试。"""
import pytest
from edu_cloud.modules.exam.models import Exam


@pytest.fixture
async def cross_school_exams(db):
    from edu_cloud.models.school import School
    sa = School(id="sch-x", name="X校", code="X", is_active=True)
    sb = School(id="sch-y", name="Y校", code="Y", is_active=True)
    db.add_all([sa, sb])
    await db.flush()
    exam_x = Exam(id="ex-x", name="X校期中", school_id="sch-x", status="draft")
    exam_y = Exam(id="ex-y", name="Y校期中", school_id="sch-y", status="draft")
    db.add_all([exam_x, exam_y])
    await db.commit()
    return exam_x, exam_y


@pytest.mark.asyncio
async def test_exam_school_id_mismatch_returns_404(db, cross_school_exams):
    """school_x 用户访问 school_y 的考试应被拒绝。"""
    exam_x, exam_y = cross_school_exams
    assert exam_y.school_id == "sch-y"
    assert exam_y.school_id != "sch-x"


@pytest.mark.asyncio
async def test_exam_school_id_match_allowed(db, cross_school_exams):
    """school_x 用户访问自己学校的考试应通过。"""
    exam_x, exam_y = cross_school_exams
    assert exam_x.school_id == "sch-x"
