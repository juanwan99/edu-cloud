from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import json
import re
from typing import Any, Iterable


BLANK_ANSWER = "空白"
EXCLUDED_QUESTIONS = {("生物", "31")}


@dataclass(frozen=True)
class BlankRecord:
    blank_no: str
    answer: str
    score: float | None
    full_score: float | None
    correct: bool
    reason: str


def normalize_question_no(qno: Any) -> str:
    text = str(qno or "").strip()
    return text[1:] if text.upper().startswith("Q") else text


def is_excluded_question(subject: Any, qno: Any) -> bool:
    return (str(subject or "").strip(), normalize_question_no(qno)) in EXCLUDED_QUESTIONS


def filter_full_data(data: dict[str, Any]) -> dict[str, Any]:
    filtered = {}
    for key, value in data.items():
        subject = value.get("subject") if isinstance(value, dict) else None
        qno = value.get("qno") if isinstance(value, dict) else None
        if not subject or qno is None:
            subject, qno = _subject_qno_from_key(key)
        if not is_excluded_question(subject, qno):
            filtered[key] = value
    return filtered


def filter_analysis_data(data: dict[str, Any]) -> dict[str, Any]:
    filtered = {}
    for subject, questions in data.items():
        if not isinstance(questions, dict):
            continue
        kept = {
            str(qno): value
            for qno, value in questions.items()
            if not is_excluded_question(subject, qno)
        }
        if kept:
            filtered[subject] = kept
    return filtered


def parse_ai_raw_response(raw: Any) -> dict[str, Any]:
    payload = _loads_json_object(raw)
    raw_content = payload.get("raw_content")
    nested = _loads_json_object(raw_content)
    return nested or payload


def iter_blank_records(raw: Any) -> Iterable[BlankRecord]:
    payload = parse_ai_raw_response(raw)
    details = payload.get("details") or []
    if not isinstance(details, list):
        return

    for detail in details:
        if not isinstance(detail, dict):
            continue
        blanks = detail.get("blanks") or []
        if not isinstance(blanks, list):
            continue
        for blank in blanks:
            if not isinstance(blank, dict):
                continue
            score = _to_float(blank.get("score"))
            full_score = _to_float(blank.get("fullScore"))
            explicit_correct = blank.get("correct")
            correct = (
                _parse_bool(explicit_correct)
                if explicit_correct is not None
                else _is_full_score(score, full_score)
            )
            yield BlankRecord(
                blank_no=_blank_no(detail, blank),
                answer=normalize_answer(blank.get("answer")),
                score=score,
                full_score=full_score,
                correct=correct,
                reason=str(blank.get("reason") or "").strip(),
            )


def summarize_blanks(
    records: Iterable[BlankRecord | dict[str, Any]],
    limit: int = 10,
    min_sample: int = 10,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[BlankRecord]] = defaultdict(list)
    for raw_record in records:
        record = _as_record(raw_record)
        grouped[record.blank_no].append(record)

    summaries = []
    for blank_no in sorted(grouped, key=_natural_key):
        blank_records = grouped[blank_no]
        total = len(blank_records)
        if total < min_sample:
            continue
        correct = 0
        wrong = 0
        blank = 0
        answer_counts: Counter[str] = Counter()
        answer_first_seen: dict[str, int] = {}
        reason_counts: Counter[str] = Counter()
        reason_first_seen: dict[str, int] = {}
        answer_reason_counts: dict[str, Counter[str]] = defaultdict(Counter)
        answer_reason_first_seen: dict[tuple[str, str], int] = {}
        full_scores: Counter[float] = Counter()

        for index, record in enumerate(blank_records):
            if record.full_score is not None:
                full_scores[record.full_score] += 1
            if record.correct:
                correct += 1
                continue

            if record.reason:
                reason_counts[record.reason] += 1
                reason_first_seen.setdefault(record.reason, index)

            if record.answer == BLANK_ANSWER:
                blank += 1
                continue

            wrong += 1
            answer_counts[record.answer] += 1
            answer_first_seen.setdefault(record.answer, index)
            if record.reason:
                answer_reason_counts[record.answer][record.reason] += 1
                answer_reason_first_seen.setdefault((record.answer, record.reason), index)

        max_score = _most_common_score(full_scores)
        wrong_answers = [
            {
                "answer": answer,
                "count": count,
                "reason": _top_reason_for_answer(
                    answer,
                    answer_reason_counts,
                    answer_reason_first_seen,
                ),
            }
            for answer, count in sorted(
                answer_counts.items(),
                key=lambda item: (-item[1], answer_first_seen[item[0]]),
            )[:limit]
        ]
        reasons = [
            {"reason": reason, "count": count}
            for reason, count in sorted(
                reason_counts.items(),
                key=lambda item: (-item[1], reason_first_seen[item[0]]),
            )[:limit]
        ]

        correct_rate = round((correct / total) * 100, 1) if total else 0
        avg_score = round(
            sum(
                r.score for r in blank_records if r.score is not None
            ) / total,
            2,
        ) if total else 0

        summaries.append(
            {
                "blankNo": blank_no,
                "maxScore": _clean_number(max_score),
                "total": total,
                "correct": correct,
                "wrong": wrong,
                "blank": blank,
                "correctRate": correct_rate,
                "avgScore": avg_score,
                "errorRate": round(((wrong + blank) / total) * 100, 1) if total else 0,
                "wrongAnswers": wrong_answers,
                "reasons": reasons,
            }
        )

    return summaries


def summarize_question_quality(
    *,
    avg: float,
    max_score: float | int,
    total: int,
    zero: int,
    blanks: list[dict[str, Any]],
    discrimination: float | None,
) -> dict[str, Any]:
    max_score_value = _to_float(max_score) or 0
    score_rate = round((avg / max_score_value) * 100, 1) if max_score_value else 0
    difficulty10 = round((1 - score_rate / 100) * 10, 2)
    blank_total = sum(int(blank.get("blank") or 0) for blank in blanks)
    blank_sample = sum(int(blank.get("total") or 0) for blank in blanks)
    blank_rate = round((blank_total / blank_sample) * 100, 1) if blank_sample else 0
    zero_rate = round((zero / total) * 100, 1) if total else 0
    low_discrimination = discrimination is not None and discrimination < 0.2

    issues = []
    if low_discrimination:
        issues.append("区分度偏低")
    if score_rate >= 90:
        issues.append("得分率过高")
    elif score_rate < 45:
        issues.append("得分率偏低")
    if zero_rate >= 30:
        issues.append("零分率偏高")
    if blank_rate >= 15:
        issues.append("空白率偏高")

    if not issues:
        issues.append("表现稳定")

    if difficulty10 <= 2:
        difficulty_label = "偏易"
    elif difficulty10 <= 5:
        difficulty_label = "适中"
    elif difficulty10 <= 7:
        difficulty_label = "偏难"
    else:
        difficulty_label = "很难"

    if zero_rate >= 45 or blank_rate >= 30 or (
        low_discrimination and (score_rate < 45 or score_rate >= 90 or zero_rate >= 30)
    ):
        quality_level = "重点复核"
    elif issues != ["表现稳定"]:
        quality_level = "需要关注"
    else:
        quality_level = "相对稳定"

    return {
        "scoreRate": score_rate,
        "difficulty10": difficulty10,
        "difficultyLabel": difficulty_label,
        "blankRate": blank_rate,
        "discrimination": discrimination,
        "qualityLevel": quality_level,
        "qualityIssues": issues,
    }


def normalize_answer(answer: Any) -> str:
    text = re.sub(r"\s+", " ", str(answer or "").strip())
    return text or BLANK_ANSWER


def _subject_qno_from_key(key: str) -> tuple[str, str]:
    if "_Q" not in key:
        return "", key
    subject, qno = key.split("_Q", 1)
    return subject, qno


def _loads_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    text = value.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _blank_no(detail: dict[str, Any], blank: dict[str, Any]) -> str:
    sub_question = str(detail.get("subQuestion") or "").strip()
    index = str(blank.get("index") or "").strip()
    if sub_question and index and sub_question != index:
        raw = f"{sub_question}-{index}"
    else:
        raw = index or sub_question or "1"
    return _normalize_blank_no(raw)


def _normalize_blank_no(raw: str) -> str:
    """Normalize wildly inconsistent LLM blank numbering to canonical form.

    Maps variants like '(2)-1', '2-1-1', '第2题-1', '2)-1' all to '2-1'.
    """
    nums = re.findall(r"\d+", raw)
    if not nums:
        return raw
    if len(nums) == 1:
        return nums[0]
    if len(nums) >= 3 and nums[2] in ("0", "1", nums[1]):
        nums = nums[:2]
    return "-".join(nums[:2])


def _as_record(record: BlankRecord | dict[str, Any]) -> BlankRecord:
    if isinstance(record, BlankRecord):
        return record
    score = _to_float(record.get("score"))
    full_score = _to_float(
        record.get("full_score") if "full_score" in record else record.get("fullScore")
    )
    explicit_correct = record.get("correct")
    correct = (
        bool(explicit_correct)
        if explicit_correct is not None
        else _is_full_score(score, full_score)
    )
    return BlankRecord(
        blank_no=str(record.get("blank_no") or record.get("blankNo") or "1"),
        answer=normalize_answer(record.get("answer")),
        score=score,
        full_score=full_score,
        correct=correct,
        reason=str(record.get("reason") or "").strip(),
    )


def _top_reason_for_answer(
    answer: str,
    answer_reason_counts: dict[str, Counter[str]],
    answer_reason_first_seen: dict[tuple[str, str], int],
) -> str:
    reasons = answer_reason_counts.get(answer)
    if not reasons:
        return "-"
    return sorted(
        reasons,
        key=lambda reason: (-reasons[reason], answer_reason_first_seen[(answer, reason)]),
    )[0]


def _most_common_score(scores: Counter[float]) -> float | None:
    if not scores:
        return None
    return sorted(scores, key=lambda score: (-scores[score], score))[0]


def _clean_number(value: float | None) -> int | float:
    if value is None:
        return 0
    return int(value) if float(value).is_integer() else round(value, 2)


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    return text not in ("false", "0", "no", "")


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_full_score(score: float | None, full_score: float | None) -> bool:
    return score is not None and full_score is not None and score >= full_score


def _natural_key(value: Any) -> tuple[tuple[int, int | str], ...]:
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part)
        for part in re.split(r"(\d+)", str(value))
    )
