"""Format rubric criteria items into text for LLM grading prompts."""

_ESSAY_CALIBRATION = """
【⚠️ 整体印象定档提示】
作文评分应先形成整体印象再定档，不要逐条找问题累积扣分。
人工阅卷老师的评分习惯：通读全文→整体感觉属于哪个档次→在档内微调。
错别字、语病、字数略有不足等细节瑕疵，只在档内微调时考虑，不影响整体定档。"""


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

    result = "\n---\n".join(parts)

    # 有 essayAnchors 字段 → 作文题，追加整体定档提示 + 锚定范文
    if len(items) == 1 and items[0].get("essayAnchors"):
        result += "\n" + _ESSAY_CALIBRATION
        anchors = items[0].get("essayAnchors")
        if anchors and isinstance(anchors, list):
            valid = [a for a in anchors if a and a.get("summary")]
            if valid:
                result += "\n\n【评分参照样本】以下是同场考试的人工评分样本，帮助你校准整体印象：\n"
                for a in valid:
                    tier = a.get("tier", "")
                    score = a.get("score", "?")
                    summary = a.get("summary", "")
                    result += f"\n■ {tier}（人工评分: {score}分）\n{summary}\n"

    return result
