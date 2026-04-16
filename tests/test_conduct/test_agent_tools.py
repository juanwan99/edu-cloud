"""Conduct Agent 工具注册测试"""
import pytest
import edu_cloud.ai.tools  # noqa: F401 — trigger registration
from edu_cloud.ai.registry import tools


def test_conduct_tools_registered():
    """6 个 conduct 工具已注册"""
    conduct_tools = [t for t in tools.get_all_specs() if t.module_code == 'conduct']
    assert len(conduct_tools) == 6


def test_conduct_tool_names():
    """验证 6 个工具名称完整"""
    names = {t.name for t in tools.get_all_specs() if t.module_code == 'conduct'}
    expected = {
        'get_conduct_rankings', 'get_student_conduct_summary',
        'get_conduct_records', 'add_conduct_points',
        'get_conduct_rules', 'get_class_conduct_overview',
    }
    assert names == expected


def test_add_conduct_points_is_medium_risk():
    """add_conduct_points 是 medium 风险且非只读"""
    tool = tools.get('add_conduct_points')
    assert tool is not None
    assert tool.risk_level == 'medium'
    assert not tool.is_read_only


def test_read_only_tools():
    """其余 5 个工具都是只读"""
    read_only_names = {
        'get_conduct_rankings', 'get_student_conduct_summary',
        'get_conduct_records', 'get_conduct_rules',
        'get_class_conduct_overview',
    }
    for name in read_only_names:
        tool = tools.get(name)
        assert tool is not None, f"Tool {name} not found"
        assert tool.is_read_only, f"Tool {name} should be read-only"
        assert tool.risk_level == 'low', f"Tool {name} should be low risk"


def test_student_conduct_summary_sensitivity():
    """get_student_conduct_summary 应为 student 级别敏感度"""
    tool = tools.get('get_student_conduct_summary')
    assert tool is not None
    assert tool.sensitivity == 'student'


# ── F003: Agent 工具 scope 校验红测 ──

@pytest.mark.anyio
async def test_get_conduct_rankings_out_of_scope_rejected(db, school_class_student):
    """F003: class_id 不在 ctx.class_ids 中 → success=False, error 含 'out of scope'."""
    from edu_cloud.ai.tool_context import ToolContext
    from edu_cloud.ai.tools.conduct import get_conduct_rankings
    from edu_cloud.modules.student.models import Class
    school, cls_a, _ = school_class_student
    cls_b = Class(name="外班", grade="高一", grade_number=1, school_id=school.id)
    db.add(cls_b)
    await db.commit()

    ctx = ToolContext(
        db=db, school_id=school.id, user_id="u1", role="homeroom_teacher",
        class_ids=[cls_a.id],  # 只能看 A 班
    )
    # 尝试查 B 班
    result = await get_conduct_rankings({"class_id": cls_b.id}, ctx)
    assert result.success is False
    assert "out of scope" in (result.error or "")


@pytest.mark.anyio
async def test_add_conduct_points_out_of_scope_rejected(db, school_class_student):
    """F003: add_conduct_points 跨班写入必须被拒绝."""
    from edu_cloud.ai.tool_context import ToolContext
    from edu_cloud.ai.tools.conduct import add_conduct_points
    from edu_cloud.modules.student.models import Class
    school, cls_a, _ = school_class_student
    cls_b = Class(name="外班", grade="高一", grade_number=1, school_id=school.id)
    db.add(cls_b)
    await db.commit()

    ctx = ToolContext(
        db=db, school_id=school.id, user_id="u1", role="subject_teacher",
        class_ids=[cls_a.id],
    )
    # 尝试给 B 班加分
    result = await add_conduct_points(
        {"student_name": "张三", "class_id": cls_b.id, "points": 5, "reason": "越权"}, ctx,
    )
    assert result.success is False
    assert "out of scope" in (result.error or "")


@pytest.mark.anyio
async def test_get_student_conduct_summary_out_of_scope_rejected(db, school_class_student):
    """F003: get_student_conduct_summary 跨班读 → 拒绝."""
    from edu_cloud.ai.tool_context import ToolContext
    from edu_cloud.ai.tools.conduct import get_student_conduct_summary
    from edu_cloud.modules.student.models import Class, Student
    school, cls_a, _ = school_class_student
    cls_b = Class(name="外班", grade="高一", grade_number=1, school_id=school.id)
    db.add(cls_b)
    await db.flush()
    s_b = Student(name="李四", student_number="2026002", class_id=cls_b.id, school_id=school.id)
    db.add(s_b)
    await db.commit()

    ctx = ToolContext(
        db=db, school_id=school.id, user_id="u1", role="homeroom_teacher",
        class_ids=[cls_a.id],
    )
    result = await get_student_conduct_summary({"student_id": s_b.id}, ctx)
    assert result.success is False
    assert "out of scope" in (result.error or "")


@pytest.mark.anyio
async def test_get_conduct_rankings_none_scope_allows_all(db, school_class_student):
    """F003: ctx.class_ids=None（校级+ 角色）→ 任意 class_id 都放行."""
    from edu_cloud.ai.tool_context import ToolContext
    from edu_cloud.ai.tools.conduct import get_conduct_rankings
    school, cls_a, _ = school_class_student
    ctx = ToolContext(
        db=db, school_id=school.id, user_id="u1", role="principal",
        class_ids=None,  # 全可见
    )
    result = await get_conduct_rankings({"class_id": cls_a.id}, ctx)
    assert result.success is True
