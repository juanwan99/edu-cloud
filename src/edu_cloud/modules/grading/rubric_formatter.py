"""Format rubric criteria items into text for LLM grading prompts.

Ported from zhixue-server rubricFormatter.js.
"""


def format_rubric_for_grading(items: list[dict] | None) -> str:
    if not items:
        return ""

    parts = []
    for item in items:
        blank_no = item.get("blankNo", "?")
        score = item.get("score", 0)
        answer = item.get("standardAnswer") or item.get("answer", "")

        text = f"【第{blank_no}空】（{score}分）\n"
        text += f"标准答案：{answer}\n"

        context = item.get("context", "")
        if context:
            text += f"背景与逻辑：{context}\n"

        rules = item.get("judgingRules", "")
        if rules:
            text += f"判分规则：{rules}\n"

        parts.append(text)

    return "\n---\n".join(parts)
