"""分析报告 AI 工具测试。"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from edu_cloud.ai.tools.analytics_report import get_score_segments, compare_exams


@pytest.fixture
def mock_ctx():
    ctx = MagicMock()
    ctx.db = AsyncMock()
    ctx.school_id = "school-1"
    ctx.subject_codes = None
    ctx.class_ids = None
    ctx.data_scope = None
    return ctx


async def test_compare_exams_missing_exam_ids(mock_ctx):
    """缺少 exam_ids 应返回明确错误。"""
    result = await compare_exams({"target_type": "grade"}, mock_ctx)
    assert result.success is False
    assert "exam_ids" in result.error


async def test_compare_exams_missing_target_id_for_class(mock_ctx):
    """class 维度缺 target_id → 错误。"""
    result = await compare_exams({"exam_ids": ["e1"], "target_type": "class"}, mock_ctx)
    assert result.success is False
    assert "target_id" in result.error


async def test_generate_analysis_report_success(db):
    """generate_analysis_report 应创建 Studio Document 并完成状态流转。"""
    from edu_cloud.models.school import School
    from edu_cloud.models.user import User
    from edu_cloud.models.exam import Exam, Subject, Question
    from edu_cloud.modules.scan.models import StudentAnswer
    from edu_cloud.modules.grading.models import GradingTask, GradingResult
    from edu_cloud.modules.student.models import Class, Student
    from edu_cloud.ai.tools.analytics_report import generate_analysis_report
    from edu_cloud.ai.tool_context import ToolContext
    from datetime import datetime

    school = School(name="AIToolSchool", code="AIT01")
    db.add(school)
    await db.commit()

    cls = Class(name="一班", grade="七年级", school_id=school.id)
    db.add(cls)
    await db.commit()

    stu = Student(name="张三", student_number="T001", class_id=cls.id, school_id=school.id)
    db.add(stu)
    await db.commit()

    user = User(username="ait_user", display_name="U")
    user.set_password("p")
    db.add(user)
    await db.commit()

    exam = Exam(name="AI工具测试考试", school_id=school.id, exam_date=datetime(2026, 3, 15))
    db.add(exam)
    await db.commit()
    subj = Subject(exam_id=exam.id, name="数学", code="math", school_id=school.id)
    db.add(subj)
    await db.commit()
    q = Question(subject_id=subj.id, name="Q1", question_type="choice", max_score=100.0, school_id=school.id)
    db.add(q)
    await db.commit()

    task = GradingTask(subject_id=subj.id, school_id=school.id, status="completed", total=1, completed=1, failed=0, created_by=user.id)
    db.add(task)
    await db.commit()

    ans = StudentAnswer(exam_id=exam.id, subject_id=subj.id, student_id=stu.id, question_id=q.id, image_path="/fake.png", school_id=school.id)
    db.add(ans)
    await db.flush()
    gr = GradingResult(answer_id=ans.id, question_id=q.id, ai_score=85.0, final_score=85.0, max_score=100.0, school_id=school.id, ai_task_id=task.id)
    db.add(gr)
    await db.commit()

    ctx = ToolContext(db=db, school_id=school.id, user_id=user.id, role="academic_director")
    result = await generate_analysis_report({"exam_ids": [exam.id]}, ctx)
    assert result.success is True
    assert "document_id" in result.data
    assert result.data["status"] == "executed"

    # Verify document exists in DB
    from sqlalchemy import select
    from edu_cloud.models.document import Document
    doc = (await db.execute(select(Document).where(Document.id == result.data["document_id"]))).scalar_one()
    assert doc.status == "executed"
    assert doc.type == "analysis_report"


async def test_compare_exams_student_visibility_check(mock_ctx):
    """homeroom_teacher 不能通过 AI 工具查看外班学生趋势。"""
    mock_ctx.class_ids = ["class-1"]
    # Mock Student query to return class-2
    mock_row = MagicMock()
    mock_row.class_id = "class-2"
    mock_result = MagicMock()
    mock_result.first.return_value = mock_row
    mock_ctx.db.execute = AsyncMock(return_value=mock_result)

    result = await compare_exams({"exam_ids": ["e1"], "target_type": "student", "target_id": "stu-1"}, mock_ctx)
    assert result.success is False
    assert "无权" in result.error
