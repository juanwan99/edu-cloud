"""Post-LLM equivalence guard: force full score when answer exactly matches equivalentAnswers."""

import re

_NORMALIZE_RE = re.compile(r'[\s　.,，。、；;：:！!？?“”‘’"\'()（）\[\]【】{}]+')


def _normalize(text: str) -> str:
    return _NORMALIZE_RE.sub('', text).strip().lower()


def apply_equivalence_guard(
    grade_result: dict,
    criteria: list[dict],
) -> dict:
    """Check each blank: if student answer exactly matches any equivalent answer
    but LLM gave less than full score, force it to full score.

    Mutates and returns grade_result.
    """
    if not criteria or not grade_result:
        return grade_result

    eq_map: dict[str, tuple[float, set[str]]] = {}
    for item in criteria:
        bn = str(item.get("blankNo", ""))
        score = float(item.get("score", 0))
        answer = item.get("standardAnswer") or item.get("answer", "")
        all_answers = set()
        if answer:
            all_answers.add(_normalize(answer))
        eq = item.get("equivalentAnswers")
        if eq and isinstance(eq, list):
            for a in eq:
                if a:
                    all_answers.add(_normalize(str(a)))
        if all_answers:
            eq_map[bn] = (score, all_answers)

    if not eq_map:
        return grade_result

    corrected = 0
    details = grade_result.get("details", [])
    for sub in details:
        for blank in sub.get("blanks", []):
            idx = blank.get("index", 0)
            sub_q = sub.get("subQuestion", "").replace("(", "").replace(")", "")
            bn = f"{sub_q}-{idx}" if sub_q else str(idx)

            student_ans = _normalize(str(blank.get("answer", "")))
            if not student_ans:
                continue

            eq_entry = eq_map.get(bn)
            if not eq_entry:
                continue

            full_score, valid_answers = eq_entry
            if student_ans in valid_answers and blank.get("score", 0) < full_score:
                blank["score"] = full_score
                blank["correct"] = True
                blank["reason"] = "命中等价答案"
                corrected += 1

    if corrected > 0:
        for sub in details:
            sub["score"] = sum(b.get("score", 0) for b in sub.get("blanks", []))
        grade_result["score"] = sum(s.get("score", 0) for s in details)

    return grade_result
