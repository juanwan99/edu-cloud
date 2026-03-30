"""作业 Agent 工具测试。"""
import pytest


@pytest.mark.asyncio
async def test_homework_tools_registered():
    """5 个作业工具已注册到 registry。"""
    import edu_cloud.ai.tools  # noqa: F401 — trigger all tool registrations
    from edu_cloud.ai.registry import tools
    all_names = [t.name for t in tools.get_all_specs()]
    expected = [
        "list_homework_tasks", "get_homework_stats",
        "get_submission_details", "assign_homework", "recommend_remedial",
    ]
    for name in expected:
        assert name in all_names, f"工具 {name} 未注册"


@pytest.mark.asyncio
async def test_homework_tools_capabilities():
    """F-05/F-08: 所有 homework 工具的 requires_capabilities 已填。"""
    import edu_cloud.ai.tools  # noqa: F401
    from edu_cloud.ai.registry import tools
    hw_tools = [t for t in tools.get_all_specs() if t.module_code == "homework"]
    assert len(hw_tools) == 5
    for t in hw_tools:
        assert t.requires_capabilities, f"工具 {t.name} 缺少 requires_capabilities"
    # write 工具需要 homework.write capability
    assign_tool = next(t for t in hw_tools if t.name == "assign_homework")
    assert ("homework", "write") in assign_tool.requires_capabilities
    # read 工具需要 homework.read capability
    list_tool = next(t for t in hw_tools if t.name == "list_homework_tasks")
    assert ("homework", "read") in list_tool.requires_capabilities


@pytest.mark.asyncio
async def test_list_homework_tasks_tool(db):
    """list_homework_tasks 工具返回作业列表。"""
    from edu_cloud.ai.tools.homework import list_homework_tasks
    from edu_cloud.models.school import School

    school = School(name="工具测试校", code="HWTOOL", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    result = await list_homework_tasks(_db=db, _school_id=school.id)
    assert "tasks" in result
    assert len(result["tasks"]) == 0


@pytest.mark.asyncio
async def test_recommend_remedial_stub():
    """recommend_remedial 返回 stub 消息。"""
    from edu_cloud.ai.tools.homework import recommend_remedial
    result = await recommend_remedial(exam_id="any", _db=None, _school_id="any")
    assert "开发中" in result.get("message", "") or "developing" in str(result).lower()


@pytest.mark.asyncio
async def test_assign_homework_tool(db):
    """assign_homework 工具创建并发布作业。"""
    from edu_cloud.ai.tools.homework import assign_homework
    from edu_cloud.models.school import School
    from edu_cloud.models.user import User
    from edu_cloud.models.class_group import ClassGroup

    school = School(name="Agent分配校", code="HWAGENT", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    teacher = User(username="agent_teacher", display_name="Agent老师")
    teacher.set_password("123456")
    db.add(teacher)
    await db.flush()

    cls = ClassGroup(name="九年级1班", grade="九年级", grade_number=9, school_id=school.id)
    db.add(cls)
    await db.flush()

    result = await assign_homework(
        title="Agent布置的作业", subject_code="SX",
        class_id=cls.id, deadline="",
        _db=db, _school_id=school.id, _user_id=teacher.id,
    )
    assert "task_id" in result
    assert result["status"] == "active"
