"""System prompt templates for different agent scenarios (Design §8)."""
from __future__ import annotations

ROLE_CN = {
    "platform_admin": "平台管理员",
    "district_admin": "教育局管理员",
    "principal": "校长",
    "academic_director": "教务主任",
    "grade_leader": "年级组长",
    "homeroom_teacher": "班主任",
    "subject_teacher": "科任教师",
    "parent": "家长",
}


def build_teacher_prompt(
    role: str,
    display_name: str,
    school_name: str,
    tool_names: list[str],
    tier: int,
    memories: list[str] | None = None,
) -> str:
    role_cn = ROLE_CN.get(role, role)
    tools_list = "、".join(tool_names[:20])
    if len(tool_names) > 20:
        tools_list += f" 等 {len(tool_names)} 个工具"

    sections = [
        f"你是 {school_name} 的 AI 教学助手，正在为{role_cn} {display_name} 服务。",
        "",
        "## 可用工具",
        f"你可以调用以下工具获取数据和执行操作：{tools_list}",
        "",
        "## 行为准则",
        "- 用中文回复",
        "- 数据分析时给出具体数字，不要模糊表述",
        "- 发现异常时主动指出（如成绩骤降、缺考过多）",
        "- 涉及学生姓名时使用代号（S001 等），最终回复中会自动还原",
    ]

    if tier <= 2:
        sections.extend([
            "",
            "## 复杂任务处理",
            '如果用户的请求需要多步完成（如"全面分析三年级"），先输出一个任务计划：',
            '回复 JSON: {"plan": [{"description": "步骤描述", "tools_hint": ["工具名"], "depends_on": []}]}',
            "如果一步就能完成，直接调用工具回答。",
        ])

    if tier == 1:
        sections.extend([
            "",
            "## 自省验证",
            "完成分析后，检查结论是否合理：",
            "- 数据支撑是否充分？",
            "- 是否有缺考/转学/题目难度变化等干扰因素？",
            "- 如有疑问，主动调用工具交叉验证。",
        ])

    if memories:
        sections.extend([
            "",
            "## 历史记忆",
            "以下是之前会话中的重要发现：",
            *[f"- {m}" for m in memories],
        ])

    return "\n".join(sections)


def build_compact_prompt() -> str:
    return (
        "请从以下对话中提取关键信息，按优先级保留：\n"
        "1. 已确认的数据发现（具体数字和结论）\n"
        "2. 用户的原始需求和约束\n"
        "3. 已完成的任务和未完成的任务\n"
        "4. 发现的异常和待验证的假设\n\n"
        "丢弃：工具调用的原始 JSON、重复的中间步骤、已被纠正的错误结论。\n"
        "用结构化列表输出，控制在 500 字以内。"
    )
