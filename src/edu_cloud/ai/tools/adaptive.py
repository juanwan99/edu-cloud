from edu_cloud.ai.registry import tools
from edu_cloud.ai.tool_context import ToolContext, ToolResult
from edu_cloud.modules.adaptive.service import diagnose_and_recommend


@tools.register(
    name="diagnose_and_recommend",
    description="诊断学生知识掌握状态，推荐学习路径和练习题目。返回每个DA的掌握概率、4态分类、补洞路径和推荐题目。",
    category="L6_adaptive",
    domain="adaptive",
    risk_level="low",
    is_read_only=True,
    sensitivity="student",
    parameters={
        "student_id": {"type": "string", "description": "学生ID（必填）"},
    },
)
async def tool_diagnose_and_recommend(input: dict, ctx: ToolContext) -> ToolResult:
    student_id = input.get("student_id")
    if not student_id:
        return ToolResult(success=False, error="需要 student_id 参数")

    result = await diagnose_and_recommend(
        ctx.db,
        student_id=student_id,
        school_id=ctx.school_id,
    )

    da_summary = []
    for da in result["da_states"]:
        da_summary.append(
            f"- {da['da_id']}: 掌握率{da['mastery']:.0%} ({da['state']}), "
            f"已答{da['attempt_count']}题"
        )

    path_summary = []
    for item in result["learning_path"]:
        path_summary.append(
            f"- {item['study_unit_id']} (差距分{item['gap_score']:.2f}, 状态{item['state']})"
        )

    return ToolResult(success=True, data={
        "diagnosis": "\n".join(da_summary) if da_summary else "暂无作答数据",
        "learning_path": "\n".join(path_summary) if path_summary else "所有知识点已掌握",
        "recommended_questions": result["recommended_questions"],
        "raw": result,
    })
