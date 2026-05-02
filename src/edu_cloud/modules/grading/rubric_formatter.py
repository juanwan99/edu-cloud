"""Format rubric criteria items into text for LLM grading prompts."""


def format_rubric_for_grading(items: list[dict] | None) -> str:
    if not items:
        return ""

    # 检测 swappableWith 关系，生成互换提示
    swap_groups: dict[str, list[str]] = {}
    for item in items:
        sw = item.get("swappableWith")
        if sw:
            bn = item.get("blankNo", "?")
            key = tuple(sorted([bn, sw]))
            swap_groups.setdefault(str(key), [bn, sw])

    parts = []
    for item in items:
        blank_no = item.get("blankNo", "?")
        score = item.get("score", 0)
        answer = item.get("standardAnswer") or item.get("answer", "")

        text = f"【第{blank_no}空】（{score}分）\n"
        text += f"标准答案：{answer}\n"

        eq = item.get("equivalentAnswers")
        if eq and isinstance(eq, list) and len(eq) > 0:
            text += f"等价答案（必须给满分）：{' / '.join(str(a) for a in eq)}\n"

        context = item.get("context", "")
        if context:
            text += f"背景与逻辑：{context}\n"

        rules = item.get("judgingRules", "")
        if rules:
            text += f"判分规则：{rules}\n"

        scoring = item.get("scoringRules")
        if scoring and isinstance(scoring, list):
            lines = [f"  - {r['condition']} → {r['score']}分" for r in scoring if isinstance(r, dict)]
            if lines:
                text += f"得分梯度：\n" + "\n".join(lines) + "\n"

        exclusion = item.get("exclusionRules")
        if exclusion and isinstance(exclusion, list):
            lines = [f"  - {r['pattern']}（{r.get('reason', '')}）" for r in exclusion if isinstance(r, dict)]
            if lines:
                text += f"排除项（直接0分）：\n" + "\n".join(lines) + "\n"

        wrong = item.get("typicalWrongAnswers")
        if wrong and isinstance(wrong, list) and len(wrong) > 0:
            text += f"典型错误：{' / '.join(str(w) for w in wrong)}\n"

        sw = item.get("swappableWith")
        if sw:
            text += f"⚠️ 本空与第{sw}空答案可互换（顺序不影响得分）\n"

        parts.append(text)

    return "\n---\n".join(parts)
