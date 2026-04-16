from edu_cloud.ai.prompts import build_teacher_prompt, build_compact_prompt


def test_teacher_prompt_contains_role():
    prompt = build_teacher_prompt(
        role="academic_director",
        display_name="张老师",
        school_name="实验中学",
        tool_names=["get_exam_summary", "get_class_stats"],
        tier=2,
    )
    assert "张老师" in prompt
    assert "教务主任" in prompt
    assert "get_exam_summary" in prompt


def test_teacher_prompt_tier1_has_plan_instruction():
    prompt = build_teacher_prompt(role="teacher", display_name="李老师", school_name="一中",
                                  tool_names=["t1"], tier=1)
    assert "计划" in prompt or "plan" in prompt.lower()


def test_teacher_prompt_tier3_no_plan_instruction():
    prompt = build_teacher_prompt(role="teacher", display_name="王老师", school_name="二中",
                                  tool_names=["t1"], tier=3)
    assert "计划" not in prompt


def test_compact_prompt():
    prompt = build_compact_prompt()
    assert "关键信息" in prompt or "摘要" in prompt
