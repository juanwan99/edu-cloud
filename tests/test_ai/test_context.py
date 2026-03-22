from edu_cloud.ai.context import build_system_prompt


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
