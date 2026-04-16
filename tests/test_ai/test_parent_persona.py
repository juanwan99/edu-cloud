"""Tests for parent_advisor persona prompt + get_student_profile domain tool."""
import pytest
from sqlalchemy import select

from edu_cloud.ai.tool_context import ToolContext, ToolResult
from edu_cloud.models.school import School
from edu_cloud.modules.exam.models import Exam
from edu_cloud.modules.knowledge.models import KnowledgePoint
from edu_cloud.modules.profile.models import StudentExamSnapshot, StudentKnowledgeMastery
from edu_cloud.modules.student.models import Student


# ---------------------------------------------------------------------------
# build_parent_prompt tests
# ---------------------------------------------------------------------------


def test_build_parent_prompt_is_warm():
    from edu_cloud.ai.prompts import build_parent_prompt

    prompt = build_parent_prompt(child_name="小明", school_name="育才中学")
    assert "小明" in prompt
    assert "鼓励" in prompt or "建议" in prompt
    assert "不要提供排名信息" in prompt  # default: no rankings allowed


def test_build_parent_prompt_with_rankings():
    from edu_cloud.ai.prompts import build_parent_prompt

    prompt = build_parent_prompt(
        child_name="小红", school_name="实验中学", can_see_rankings=True
    )
    assert "小红" in prompt
    assert "实验中学" in prompt
    # when can_see_rankings=True, the "no rankings" note should be absent
    assert "不要提供排名信息" not in prompt


def test_build_parent_prompt_no_rankings_note():
    from edu_cloud.ai.prompts import build_parent_prompt

    prompt = build_parent_prompt(
        child_name="小刚", school_name="三中", can_see_rankings=False
    )
    assert "不要提供排名信息" in prompt


# ---------------------------------------------------------------------------
# get_student_profile tool tests
# ---------------------------------------------------------------------------


@pytest.fixture
async def profile_seed(db):
    """Seed school + student + snapshots + mastery for profile tool tests."""
    school = School(name="画像测试校", code="PROFILE01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    student = Student(
        name="王五", student_number="P001", school_id=school.id,
        class_id=None, grade="八年级",
    )
    db.add(student)
    await db.flush()

    exam = Exam(name="期中考试", school_id=school.id, semester="2025-2026-2")
    db.add(exam)
    await db.flush()

    # Snapshot
    db.add(StudentExamSnapshot(
        student_id=student.id, exam_id=exam.id, subject_code="math",
        total_score=88.0, max_score=100.0, score_rate=0.88,
        class_rank=5, school_id=school.id,
    ))

    # Knowledge mastery (weak point: mastery < 0.6)
    kp = KnowledgePoint(code="MATH-W01", name="二次函数", course_code="math", school_id=school.id)
    db.add(kp)
    await db.flush()

    db.add(StudentKnowledgeMastery(
        student_id=student.id, knowledge_point_id=kp.id,
        mastery_level=0.35, attempt_count=4, school_id=school.id,
    ))

    # A well-mastered knowledge point (should NOT appear in weak_points)
    kp2 = KnowledgePoint(code="MATH-S01", name="一元一次方程", course_code="math", school_id=school.id)
    db.add(kp2)
    await db.flush()

    db.add(StudentKnowledgeMastery(
        student_id=student.id, knowledge_point_id=kp2.id,
        mastery_level=0.9, attempt_count=10, school_id=school.id,
    ))

    await db.commit()
    from types import SimpleNamespace
    return SimpleNamespace(school_id=school.id, student_id=student.id, exam_id=exam.id)


@pytest.mark.asyncio
async def test_get_student_profile_returns_data(db, profile_seed):
    from edu_cloud.ai.tools.student_profile_tool import get_student_learning_profile

    ctx = ToolContext(db=db, school_id=profile_seed.school_id, user_id="u1", role="parent")
    result = await get_student_learning_profile({"student_id": profile_seed.student_id}, ctx)

    assert result.success is True
    assert result.data["exam_count"] == 1
    assert result.data["latest_score_rate"] == 0.88
    assert len(result.data["trend"]) == 1
    assert result.data["trend"][0]["score_rate"] == 0.88
    # Only the weak point (mastery < 0.6) should appear
    assert len(result.data["weak_points"]) == 1
    assert result.data["weak_points"][0]["mastery"] == 0.35


@pytest.mark.asyncio
async def test_parent_cannot_see_rank(db, profile_seed):
    """F1: Parent role should not see class_rank in trend data."""
    from edu_cloud.ai.tools.student_profile_tool import get_student_learning_profile

    ctx = ToolContext(db=db, school_id=profile_seed.school_id, user_id="u1", role="parent")
    result = await get_student_learning_profile({"student_id": profile_seed.student_id}, ctx)

    assert result.success is True
    assert "rank" not in result.data["trend"][0]


@pytest.mark.asyncio
async def test_teacher_can_see_rank(db, profile_seed):
    """F1: Non-parent roles should still see class_rank in trend data."""
    from edu_cloud.ai.tools.student_profile_tool import get_student_learning_profile

    ctx = ToolContext(db=db, school_id=profile_seed.school_id, user_id="u1", role="subject_teacher")
    result = await get_student_learning_profile({"student_id": profile_seed.student_id}, ctx)

    assert result.success is True
    assert "rank" in result.data["trend"][0]
    assert result.data["trend"][0]["rank"] == 5


@pytest.mark.asyncio
async def test_get_student_profile_no_data(db):
    # Create a school so school_id is valid but no student data
    school = School(name="空数据校", code="EMPTY01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()
    await db.commit()

    from edu_cloud.ai.tools.student_profile_tool import get_student_learning_profile

    ctx = ToolContext(db=db, school_id=school.id, user_id="u1", role="parent")
    result = await get_student_learning_profile({"student_id": "nonexistent"}, ctx)

    assert result.success is True
    assert result.data["status"] == "no_data"


@pytest.mark.asyncio
async def test_get_student_profile_with_subject_filter(db, profile_seed):
    from edu_cloud.ai.tools.student_profile_tool import get_student_learning_profile

    ctx = ToolContext(db=db, school_id=profile_seed.school_id, user_id="u1", role="parent")

    # Filter by math — should return data
    result = await get_student_learning_profile(
        {"student_id": profile_seed.student_id, "subject_code": "math"}, ctx
    )
    assert result.success is True
    assert result.data["exam_count"] == 1

    # Filter by english — should return no_data
    result = await get_student_learning_profile(
        {"student_id": profile_seed.student_id, "subject_code": "english"}, ctx
    )
    assert result.success is True
    assert result.data["status"] == "no_data"
