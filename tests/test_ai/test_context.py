from edu_cloud.ai.context import build_system_prompt, AgentContext


def test_system_prompt_contains_role():
    prompt = build_system_prompt(
        role="homeroom_teacher", display_name="张老师",
        scope={"school": "实验中学", "classes": ["七年级2班"]},
        tool_names=["get_exam_scores", "get_class_stats"],
    )
    assert "张老师" in prompt
    assert "班主任" in prompt or "homeroom_teacher" in prompt
    assert "七年级2班" in prompt
    assert "get_exam_scores" in prompt


def test_system_prompt_without_scope():
    prompt = build_system_prompt(
        role="platform_admin", display_name="管理员", scope={}, tool_names=["get_exam_scores"],
    )
    assert "管理员" in prompt


def test_agent_context_build_messages():
    ctx = AgentContext(system_content="你是助手")
    ctx.add_user_message("你好", "s1")
    messages = ctx.build_messages("s1")
    assert len(messages) == 2
    assert messages[0].role == "system"
    assert messages[0].content == "你是助手"
    assert messages[1].role == "user"
    assert messages[1].content == "你好"


def test_agent_context_multi_turn():
    ctx = AgentContext(system_content="系统提示")
    ctx.add_user_message("问题1", "s1")
    ctx.add_assistant_message("回答1", "s1")
    ctx.add_user_message("问题2", "s1")
    messages = ctx.build_messages("s1")
    assert len(messages) == 4  # system + user + assistant + user


def test_agent_context_session_isolation():
    ctx = AgentContext(system_content="系统提示")
    ctx.add_user_message("会话A", "a")
    ctx.add_user_message("会话B", "b")
    assert len(ctx.build_messages("a")) == 2  # system + 1 user
    assert len(ctx.build_messages("b")) == 2


def test_agent_context_clear_session():
    ctx = AgentContext(system_content="系统提示")
    ctx.add_user_message("你好", "s1")
    ctx.clear_session("s1")
    assert len(ctx.build_messages("s1")) == 1  # only system
