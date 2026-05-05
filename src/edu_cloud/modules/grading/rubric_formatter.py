"""Format rubric criteria items into text for LLM grading prompts."""

_ESSAY_CALIBRATION = """
【⚠️ 整体印象定档提示】
作文评分应先形成整体印象再定档，不要逐条找问题累积扣分。
人工阅卷老师的评分习惯：通读全文→整体感觉属于哪个档次→在档内微调。
错别字、语病、字数略有不足等细节瑕疵，只在档内微调时考虑，不影响整体定档。"""


def split_essay_anchors(anchors: list[dict]) -> tuple[list[dict], list[dict]]:
    """将 essayAnchors 拆为 3 锚（主评）和 5 锚（confirm）两组。

    anchors 按 score 降序排列。至少需要 3 个锚点才能生效。
    3 锚取最后 3 个（最低分三档：如 42/38/35）用于主评。
    5 锚取全部（如 46/43/42/38/35）用于 confirm。
    返回 (anchors_3, anchors_5)。
    """
    valid = [a for a in (anchors or []) if a and a.get("summary")]
    valid.sort(key=lambda a: a.get("score", 0), reverse=True)
    if len(valid) < 3:
        return [], []
    a3 = valid[-3:]  # 最低 3 个
    a5 = valid        # 全部
    return a3, a5


def build_essay_anchor_prompt(
    ocr_text: str,
    char_stats: str,
    anchors: list[dict],
    *,
    mode: str = "score",
) -> str:
    """构建作文锚点评分 prompt。

    mode="score" → 3 锚主评（输出 score 0-42 + above_boundary）
    mode="confirm" → 5 锚确认（输出 score，逐级比较）
    """
    header = "你是自动作文评分器，满分50。依据锚点样本评分。\n\n【锚点样本】\n\n"
    parts = []
    for a in anchors:
        sc = a.get("score", "?")
        summary = (a.get("summary") or "")[:700]
        reason = a.get("reason", "")
        parts.append(f"■ {sc}分样本\n{summary}\n{sc}分: {reason}\n")

    body = header + "\n".join(parts)
    body += f"\n【目标作文】\n{ocr_text}\n\n{char_stats}\n\n---\n"

    if mode == "score":
        body += (
            "【方法】按以下顺序评分：\n"
            "1. 先判定是否为无效作文（纯数据罗列/抄题/无中心无情感→invalid，正常作文→normal）\n"
            "2. 再判定完成度（complete=完整/unfinished=明显未写完无结尾/rushed=仓促收尾）\n"
            "3. 再判定文体（event=有具体事件/reflective=感悟议论为主但扣题完整/listing=堆砌罗列）\n"
            "4. 最后和38分比较定位。OCR噪声不扣分。标题不限看内容。\n\n"
            "⚠️ 无效作文（纯罗列/无中心/不成文）不参与锚点比较，直接给0-15分。\n"
            "⚠️ 感悟/议论式记叙文只要扣题+完整+通顺，不应仅因缺少具体场景压到低档。\n"
            "如果明显强于42分样本，score不超过42，设above_boundary=true。\n\n"
            '【输出JSON】{"score": 整数(0-42), "above_boundary": true或false, '
            '"validity": "normal或invalid", '
            '"completion": "complete或unfinished或rushed", '
            '"style": "event或reflective或listing", '
            '"reason": "理由(<=40字)"}\n'
        )
    elif mode == "low_review":
        body = (
            "你是作文低分复核评分器。一位评分器给出了低于32分的初评，请复核确认。\n\n"
            "【低分段标准】\n"
            "0-15分：空白/抄题/完全跑题/通篇数字符号\n"
            "16-25分：严重偏题、内容极度空洞、逻辑混乱不成文、大段重复\n"
            "26-34分：基本切题但内容单薄、结构松散、语言表达问题多\n"
            "35分以上：切题完整、有真实叙事或论述\n\n"
            f"【目标作文】\n{ocr_text}\n\n{char_stats}\n\n---\n"
            "【任务】判断这篇作文属于哪个分段，给出分数。\n"
            "如果作文切题、结构完整、有具体内容，应给35分以上，不要因为瑕疵压到低分段。\n\n"
            '【输出JSON】{"confirmed_low": true或false, "score": 整数(0-42), "reason": "理由(<=40字)"}\n'
        )
        return body
    else:
        body += (
            "【方法】从38分样本开始逐级比较，定位到最接近的两个锚点之间。OCR噪声不扣分。\n\n"
            '【输出JSON】{"score": 整数, "reason": "理由(<=40字)"}\n'
        )
    return body


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

        eq = item.get("equivalentAnswers")
        all_answers = [answer] if answer else []
        if eq and isinstance(eq, list):
            for a in eq:
                if a and str(a) not in all_answers:
                    all_answers.append(str(a))

        if len(all_answers) > 1:
            text += f"候选满分答案（需完整等值且未命中排除项，才给{score}分）：{' / '.join(all_answers)}\n"
            text += "⚠️ 上述答案不是关键词池；若学生答案缺少题目要求的对象、限定、因果或形式要求，应按判分细则给部分分\n"
        else:
            text += f"标准答案：{answer}\n"

        context = item.get("context", "")
        if context:
            text += f"背景与逻辑：{context}\n"

        rules = item.get("judgingRules", "")
        if rules:
            text += f"判分细则：{rules}\n"

        scoring = item.get("scoringRules")
        if scoring and isinstance(scoring, list):
            lines = [f"  - {r['condition']} → {r['score']}分" for r in scoring if isinstance(r, dict)]
            if lines:
                text += "部分分：\n" + "\n".join(lines) + "\n"

        exclusion = item.get("exclusionRules")
        if exclusion and isinstance(exclusion, list):
            lines = [f"  - {r['pattern']}（{r.get('reason', '')}）" for r in exclusion if isinstance(r, dict)]
            if lines:
                text += "排除项（直接0分）：\n" + "\n".join(lines) + "\n"

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
            valid = [a for a in anchors if a and (a.get("summary") or a.get("reason"))]
            if valid:
                result += "\n\n【评分参照样本】以下是校准样本，帮助你校准整体印象：\n"
                for a in valid:
                    tier = a.get("tier", "")
                    score = a.get("score", "?")
                    summary = a.get("summary", "")
                    reason = a.get("reason", "")
                    result += f"\n■ {tier}（校准分: {score}分）\n{summary}\n"
                    if reason:
                        result += f"评分理由: {reason}\n"

    return result
