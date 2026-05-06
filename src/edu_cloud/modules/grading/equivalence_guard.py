"""Post-LLM equivalence guard: force full score when answer exactly matches equivalentAnswers.

Only uses equivalents declared in the rubric criteria — no hardcoded mappings.
"""

import re

_NORMALIZE_RE = re.compile(r'[\s　.,，。、；;：:！!？?""\'\'()（）\[\]【】{}]+')


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

    eq_map: dict[str, tuple[float, set[str], dict[str, str]]] = {}
    for item in criteria:
        bn = str(item.get("blankNo", ""))
        score = float(item.get("score", 0))
        answer = item.get("standardAnswer") or item.get("answer", "")
        all_answers = set()
        norm_to_orig: dict[str, str] = {}
        if answer:
            n = _normalize(answer)
            all_answers.add(n)
            norm_to_orig[n] = str(answer)
        eq = item.get("equivalentAnswers")
        if eq and isinstance(eq, list):
            for a in eq:
                if a:
                    n = _normalize(str(a))
                    all_answers.add(n)
                    if n not in norm_to_orig:
                        norm_to_orig[n] = str(a)
        if all_answers:
            eq_map[bn] = (score, all_answers, norm_to_orig)

    if not eq_map:
        return grade_result

    corrected = 0
    details = grade_result.get("details", [])
    for sub in details:
        if "blanks" not in sub and "blankNo" in sub:
            blanks_iter = [sub]
        else:
            blanks_iter = sub.get("blanks", [])
        for blank in blanks_iter:
            idx = blank.get("index", 0)
            if blank.get("blankNo"):
                bn = str(blank["blankNo"]).replace("(", "").replace(")", "")
            else:
                sub_q = sub.get("subQuestion", "").replace("(", "").replace(")", "")
                bn = f"{sub_q}-{idx}" if sub_q else str(idx)

            student_ans = _normalize(str(blank.get("answer", "")))
            if not student_ans:
                continue

            eq_entry = eq_map.get(bn)
            if not eq_entry:
                continue

            full_score, valid_answers, norm_to_orig = eq_entry
            if (
                student_ans in valid_answers
                and blank.get("score", 0) < full_score
            ):
                blank["score"] = full_score
                blank["correct"] = True
                matched_orig = norm_to_orig.get(student_ans, "")
                raw_answer = str(blank.get("answer", ""))
                if matched_orig and raw_answer and matched_orig != raw_answer:
                    blank["reason"] = f"与满分答案'{matched_orig}'等价"
                else:
                    blank["reason"] = f"与满分答案'{matched_orig or raw_answer}'一致"
                corrected += 1

    if corrected > 0:
        for sub in details:
            if "blanks" in sub:
                sub["score"] = sum(b.get("score", 0) for b in sub.get("blanks", []))
            elif "blankNo" in sub:
                pass
        grade_result["score"] = sum(s.get("score", 0) for s in details)

    return grade_result
