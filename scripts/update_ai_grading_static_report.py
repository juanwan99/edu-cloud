#!/usr/bin/env python3
"""Generate two-panel AI grading report JSON.

Panel 1 (panel1_quality): AI grading quality analysis — human vs AI score comparison.
Panel 2 (panel2_answer): Answer quality analysis — student performance diagnostics.

Output: docs/ai-grading-full-data.json (single file, published to frontend/public/ and
frontend/dist/ if it exists).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
import json
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from edu_cloud.modules.analytics.ai_grading_static_report import (  # noqa: E402
    filter_full_data,
    iter_blank_records,
    summarize_blanks,
    summarize_question_quality,
)


DB_PATH = ROOT / "edu_cloud.db"
EXAM_ID = "796f7c26-77d6-4606-ba42-a1c2de2aa4f7"
EXAM_NAME = "2026年第一学期期中考试"
PUBLISH_FILENAME = "ai-grading-full-data.json"

QUESTION_ORDER = [
    ("地理", "26"),
    ("地理", "27"),
    ("地理", "28"),
    ("语文", "4"),
    ("语文", "6"),
    ("语文", "9"),
    ("语文", "10"),
    ("语文", "12"),
    ("语文", "13"),
    ("语文", "15"),
    ("语文", "18、19"),
    ("语文", "21、22"),
    ("语文", "23"),
    ("生物", "26"),
    ("生物", "27"),
    ("生物", "28"),
    ("生物", "29"),
    ("生物", "30"),
]
ORIGINAL_QUESTION_ORDER = [*QUESTION_ORDER, ("生物", "31")]

UTC8 = timezone(timedelta(hours=8))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # Load raw rows per question (with ai_score, final_score, ai_raw_response)
        rows_by_question = {
            (subject, qno): load_question_rows(conn, subject, qno)
            for subject, qno in QUESTION_ORDER
        }
        subject_totals = build_subject_totals(rows_by_question)

        # Build per-question answer quality data (panel 2 source)
        answer_by_question = {}
        for subject, qno in QUESTION_ORDER:
            key = f"{subject}_Q{qno}"
            answer_by_question[key] = summarize_question(
                subject, qno, rows_by_question[(subject, qno)],
                subject_totals.get(subject, {}),
            )
        # Apply Q31 exclusion filter
        answer_by_question = filter_full_data(answer_by_question)

        # Build per-question quality comparison data (panel 1 source)
        comparison_rows = {
            (subject, qno): load_comparison_rows(conn, subject, qno)
            for subject, qno in QUESTION_ORDER
        }

        subjects = sorted({s for s, _ in QUESTION_ORDER})
    finally:
        conn.close()

    # Assemble the two panels
    panel1 = build_panel1_quality(comparison_rows, subjects)
    panel2 = build_panel2_answer(answer_by_question, subjects)

    output = {
        "meta": {
            "examId": EXAM_ID,
            "examName": EXAM_NAME,
            "subjects": subjects,
            "generatedAt": datetime.now(UTC8).isoformat(timespec="seconds"),
        },
        "panel1_quality": panel1,
        "panel2_answer": panel2,
    }

    # Write and publish
    docs_dir = ROOT / "docs"
    out_path = docs_dir / PUBLISH_FILENAME
    write_json(out_path, output)
    published = publish_report(docs_dir)

    # Summary
    p1_total = panel1["overall"]["totalRecords"]
    p1_exact = panel1["overall"]["exactMatchRate"]
    p1_w2 = panel1["overall"]["within2Rate"]
    p2_qcount = panel2["overall"]["questionCount"]
    print(
        f"wrote {out_path.relative_to(ROOT)}  "
        f"panel1: {p1_total} records, exactMatch={p1_exact}%, within2={p1_w2}%  "
        f"panel2: {p2_qcount} questions"
    )
    print(
        "published to "
        + ", ".join(str(p.relative_to(ROOT)) for p in published)
    )


# ---------------------------------------------------------------------------
# DB loaders
# ---------------------------------------------------------------------------

def load_question_rows(
    conn: sqlite3.Connection, subject: str, qno: str,
) -> list[sqlite3.Row]:
    """Load rows with ai_score (used for answer quality panel)."""
    return conn.execute(
        """
        SELECT sa.id AS answer_id, sa.student_id, q.max_score,
               gr.ai_score, gr.ai_raw_response
        FROM grading_results gr
        JOIN student_answers sa ON sa.id = gr.answer_id
        JOIN questions q ON q.id = gr.question_id
        JOIN subjects s ON s.id = q.subject_id
        WHERE sa.exam_id = ?
          AND s.name = ?
          AND q.name = ?
          AND gr.ai_score IS NOT NULL
        ORDER BY sa.id
        """,
        (EXAM_ID, subject, qno),
    ).fetchall()


def load_comparison_rows(
    conn: sqlite3.Connection, subject: str, qno: str,
) -> list[dict[str, Any]]:
    """Load rows where BOTH ai_score and final_score are available (for panel 1)."""
    rows = conn.execute(
        """
        SELECT gr.ai_score, gr.final_score, q.max_score, sa.student_id
        FROM grading_results gr
        JOIN student_answers sa ON sa.id = gr.answer_id
        JOIN questions q ON q.id = gr.question_id
        JOIN subjects s ON s.id = q.subject_id
        WHERE sa.exam_id = ?
          AND s.name = ?
          AND q.name = ?
          AND gr.ai_score IS NOT NULL
          AND gr.final_score IS NOT NULL
        ORDER BY sa.id
        """,
        (EXAM_ID, subject, qno),
    ).fetchall()
    return [
        {
            "ai_score": float(r["ai_score"]),
            "final_score": float(r["final_score"]),
            "max_score": float(r["max_score"]),
            "student_id": r["student_id"],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Panel 1: AI Grading Quality (human vs AI comparison)
# ---------------------------------------------------------------------------

def build_panel1_quality(
    comparison_rows: dict[tuple[str, str], list[dict[str, Any]]],
    subjects: list[str],
) -> dict[str, Any]:
    # Per-question stats
    by_question: dict[str, dict[str, Any]] = {}
    all_diffs: list[float] = []

    for subject, qno in QUESTION_ORDER:
        key = f"{subject}_Q{qno}"
        rows = comparison_rows.get((subject, qno), [])
        if not rows:
            continue
        q_stats = compute_comparison_stats(rows)
        q_stats["maxScore"] = _clean_number(rows[0]["max_score"])
        q_stats["sampleSize"] = len(rows)
        by_question[key] = q_stats
        all_diffs.extend(r["ai_score"] - r["final_score"] for r in rows)

    # Per-subject stats
    by_subject: dict[str, dict[str, Any]] = {}
    for subj in subjects:
        subj_rows = []
        for (s, qno), rows in comparison_rows.items():
            if s == subj:
                subj_rows.extend(rows)
        if subj_rows:
            by_subject[subj] = compute_subject_comparison(subj_rows)

    # Overall stats
    total_records = len(all_diffs)
    overall = build_panel1_overall(all_diffs, total_records, by_question, by_subject)

    return {
        "overall": overall,
        "bySubject": by_subject,
        "byQuestion": by_question,
    }


def compute_comparison_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute human-AI comparison metrics for a set of score pairs."""
    diffs = [r["ai_score"] - r["final_score"] for r in rows]
    abs_diffs = [abs(d) for d in diffs]
    n = len(diffs)

    exact = sum(1 for d in abs_diffs if d < 0.5)
    within_2 = sum(1 for d in abs_diffs if d <= 2)
    within_5 = sum(1 for d in abs_diffs if d <= 5)
    within_10 = sum(1 for d in abs_diffs if d <= 10)
    mae = round(sum(abs_diffs) / n, 2) if n else 0
    bias = round(sum(diffs) / n, 2) if n else 0
    ai_avg = round(sum(r["ai_score"] for r in rows) / n, 2) if n else 0
    human_avg = round(sum(r["final_score"] for r in rows) / n, 2) if n else 0
    max_diff = round(max(abs_diffs), 1) if abs_diffs else 0

    exact_rate = _rate(exact, n)
    within_2_rate = _rate(within_2, n)
    within_5_rate = _rate(within_5, n)
    within_10_rate = _rate(within_10, n)

    # Risk level based on within-2 rate
    if within_2_rate >= 95:
        risk_level = "低风险"
    elif within_2_rate >= 85:
        risk_level = "中风险"
    else:
        risk_level = "高风险"

    return {
        "mae": mae,
        "bias": bias,
        "exactMatchRate": exact_rate,
        "within2Rate": within_2_rate,
        "within5Rate": within_5_rate,
        "within10Rate": within_10_rate,
        "aiAvg": ai_avg,
        "humanAvg": human_avg,
        "maxDiff": max_diff,
        "riskLevel": risk_level,
    }


def compute_subject_comparison(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute subject-level comparison summary."""
    stats = compute_comparison_stats(rows)
    unique_students = len({r.get("student_id") for r in rows if r.get("student_id")})
    return {
        "studentCount": unique_students or len(rows),
        "bias": stats["bias"],
        "mae": stats["mae"],
        "maxDiff": stats["maxDiff"],
        "within5Rate": stats["within5Rate"],
        "within10Rate": stats["within10Rate"],
    }


def build_bias_distribution(diffs: list[float]) -> dict[str, int]:
    """Bucket diffs into bias distribution ranges."""
    buckets = {
        "<-3": 0,
        "-3~-2": 0,
        "-2~-1": 0,
        "-1~0": 0,
        "0": 0,
        "0~1": 0,
        "1~2": 0,
        "2~3": 0,
        ">3": 0,
    }
    for d in diffs:
        if d < -3:
            buckets["<-3"] += 1
        elif d < -2:
            buckets["-3~-2"] += 1
        elif d < -1:
            buckets["-2~-1"] += 1
        elif d < 0:
            buckets["-1~0"] += 1
        elif d == 0:
            buckets["0"] += 1
        elif d <= 1:
            buckets["0~1"] += 1
        elif d <= 2:
            buckets["1~2"] += 1
        elif d <= 3:
            buckets["2~3"] += 1
        else:
            buckets[">3"] += 1
    return buckets


def build_panel1_overall(
    all_diffs: list[float],
    total_records: int,
    by_question: dict[str, dict[str, Any]],
    by_subject: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    abs_diffs = [abs(d) for d in all_diffs]

    exact = sum(1 for d in abs_diffs if d < 0.5)
    within_2 = sum(1 for d in abs_diffs if d <= 2)
    mae = round(sum(abs_diffs) / total_records, 2) if total_records else 0
    bias = round(sum(all_diffs) / total_records, 2) if total_records else 0

    bias_dist = build_bias_distribution(all_diffs)

    # Generate conclusions
    conclusions = generate_quality_conclusions(
        total_records, by_question, by_subject,
        _rate(exact, total_records), _rate(within_2, total_records), mae, bias,
    )

    return {
        "totalRecords": total_records,
        "exactMatchRate": _rate(exact, total_records),
        "within2Rate": _rate(within_2, total_records),
        "avgMAE": mae,
        "avgBias": bias,
        "biasDistribution": bias_dist,
        "conclusions": conclusions,
    }


def generate_quality_conclusions(
    total: int,
    by_question: dict[str, dict[str, Any]],
    by_subject: dict[str, dict[str, Any]],
    exact_rate: float,
    within_2_rate: float,
    mae: float,
    bias: float,
) -> list[str]:
    """Auto-generate 3-5 conclusions for the principal."""
    conclusions: list[str] = []

    # 1. Overall reliability
    q_count = len(by_question)
    reliable = sum(1 for q in by_question.values() if q["within2Rate"] >= 90)
    conclusions.append(
        f"{q_count} 题中 {reliable} 题 AI 与人工评分 ±2 分符合率超过 90%，"
        f"整体{'可靠' if reliable >= q_count * 0.7 else '需要关注'}"
    )

    # 2. High-risk questions
    high_risk = [
        (key, q) for key, q in by_question.items()
        if q["riskLevel"] == "高风险"
    ]
    if high_risk:
        for key, q in high_risk[:2]:
            direction = "偏低" if q["bias"] < 0 else "偏高"
            conclusions.append(
                f"{key} AI 系统{direction} {abs(q['bias']):.1f} 分，"
                f"±2 分符合率仅 {q['within2Rate']}%，建议复核评分标准"
            )
    else:
        conclusions.append("所有题目 AI 评分均在可接受风险范围内")

    # 3. Bias direction
    if bias < -0.3:
        conclusions.append(
            f"AI 整体偏保守（平均偏低 {abs(bias):.2f} 分），"
            "对学生略有不利但不影响区分度"
        )
    elif bias > 0.3:
        conclusions.append(
            f"AI 整体偏宽松（平均偏高 {abs(bias):.2f} 分），"
            "建议抽查高分段是否虚高"
        )
    else:
        conclusions.append("AI 评分无系统性偏差，平均偏差在 ±0.3 分以内")

    # 4. Subject with largest concern
    worst_subject = max(by_subject.items(), key=lambda x: x[1]["mae"])
    if worst_subject[1]["mae"] > 1.5:
        conclusions.append(
            f"{worst_subject[0]}学科 MAE 最高（{worst_subject[1]['mae']} 分），"
            "建议备课组重点复核该学科 AI 评分"
        )

    # 5. Low-within2 specific questions (skip those already mentioned as high-risk)
    mentioned_keys = {key for key, _ in high_risk[:2]}
    low_w2 = [
        (key, q) for key, q in by_question.items()
        if q["within2Rate"] < 85 and key not in mentioned_keys
    ]
    for key, q in low_w2[:1]:
        conclusions.append(
            f"{key} ±2 分符合率仅 {q['within2Rate']}%，需教研组抽查"
        )

    return conclusions[:5]


# ---------------------------------------------------------------------------
# Panel 2: Answer Quality (student performance diagnostics)
# ---------------------------------------------------------------------------

def build_panel2_answer(
    answer_by_question: dict[str, dict[str, Any]],
    subjects: list[str],
) -> dict[str, Any]:
    # Per-question data (keep all existing fields + add new quality fields)
    by_question: dict[str, dict[str, Any]] = {}
    for key, q in answer_by_question.items():
        by_question[key] = q

    # Per-subject summary
    by_subject: dict[str, dict[str, Any]] = {}
    for subj in subjects:
        subj_questions = [
            q for q in answer_by_question.values() if q["subject"] == subj
        ]
        if subj_questions:
            by_subject[subj] = build_subject_answer_summary(subj_questions)

    # Overall summary
    overall = build_panel2_overall(answer_by_question, by_subject)

    return {
        "overall": overall,
        "bySubject": by_subject,
        "byQuestion": by_question,
    }


def build_subject_answer_summary(
    questions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build per-subject answer quality summary."""
    q_count = len(questions)
    avg_score_rate = round(
        sum(q.get("scoreRate", 0) for q in questions) / q_count, 1
    ) if q_count else 0
    avg_difficulty = round(
        sum(q.get("difficulty10", 0) for q in questions) / q_count, 1
    ) if q_count else 0

    weak = [
        f"Q{q['qno']}" for q in questions
        if q.get("scoreRate", 100) < 45
    ]
    strong = [
        f"Q{q['qno']}" for q in questions
        if q.get("scoreRate", 0) > 80
    ]

    return {
        "questionCount": q_count,
        "avgScoreRate": avg_score_rate,
        "avgDifficulty": avg_difficulty,
        "weakQuestions": weak,
        "strongQuestions": strong,
    }


def build_panel2_overall(
    answer_by_question: dict[str, dict[str, Any]],
    by_subject: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    questions = [
        q for q in answer_by_question.values()
        if q.get("total") and q.get("maxScore")
    ]
    q_count = len(questions)
    total_evals = sum(q["total"] for q in questions)

    weighted_denom = sum(
        float(q["maxScore"]) * int(q["total"]) for q in questions
    )
    weighted_score_rate = round(
        sum(float(q["avg"]) * int(q["total"]) for q in questions)
        / weighted_denom * 100, 1
    ) if weighted_denom else 0

    weighted_difficulty = round(
        sum(
            float(q.get("difficulty10") or 0)
            * float(q["maxScore"])
            * int(q["total"])
            for q in questions
        ) / weighted_denom, 1
    ) if weighted_denom else 0

    focus_questions = [
        q for q in questions if q.get("qualityLevel") != "相对稳定"
    ]
    stable_count = q_count - len(focus_questions)

    conclusions = generate_answer_conclusions(
        questions, by_subject, q_count, weighted_score_rate,
        weighted_difficulty, len(focus_questions), stable_count,
    )

    return {
        "questionCount": q_count,
        "totalEvaluations": total_evals,
        "weightedScoreRate": weighted_score_rate,
        "weightedDifficulty": weighted_difficulty,
        "focusCount": len(focus_questions),
        "stableCount": stable_count,
        "conclusions": conclusions,
    }


def generate_answer_conclusions(
    questions: list[dict[str, Any]],
    by_subject: dict[str, dict[str, Any]],
    q_count: int,
    weighted_score_rate: float,
    weighted_difficulty: float,
    focus_count: int,
    stable_count: int,
) -> list[str]:
    """Auto-generate conclusions for the answer quality panel."""
    conclusions: list[str] = []

    # 1. Overall difficulty
    if weighted_difficulty <= 3:
        diff_desc = "偏易"
    elif weighted_difficulty <= 5:
        diff_desc = "适中"
    elif weighted_difficulty <= 7:
        diff_desc = "偏难"
    else:
        diff_desc = "很难"
    conclusions.append(
        f"全卷加权难度 {weighted_difficulty}/10（{diff_desc}），"
        f"加权得分率 {weighted_score_rate}%"
    )

    # 2. Stability
    conclusions.append(
        f"{q_count} 题中 {stable_count} 题表现稳定，"
        f"{focus_count} 题需关注"
    )

    # 3. Weakest subject
    if by_subject:
        weakest = min(by_subject.items(), key=lambda x: x[1]["avgScoreRate"])
        if weakest[1]["avgScoreRate"] < 50:
            weak_qs = weakest[1].get("weakQuestions", [])
            conclusions.append(
                f"{weakest[0]}整体得分率最低（{weakest[1]['avgScoreRate']}%）"
                + (f"，薄弱题：{'、'.join(weak_qs)}" if weak_qs else "")
            )

    # 4. High zero-rate questions
    high_zero = [
        q for q in questions if q.get("zeroRate", 0) >= 20
    ]
    if high_zero:
        labels = [f"{q['subject']} Q{q['qno']}" for q in high_zero[:3]]
        conclusions.append(
            f"{'、'.join(labels)} 零分率偏高（>=20%），建议教研组关注"
        )

    # 5. Low discrimination
    low_disc = [
        q for q in questions
        if q.get("discrimination") is not None and q["discrimination"] < 0.2
    ]
    if low_disc:
        labels = [f"{q['subject']} Q{q['qno']}" for q in low_disc[:3]]
        conclusions.append(
            f"{'、'.join(labels)} 区分度偏低，"
            "高低分组差异不明显"
        )

    return conclusions[:5]


# ---------------------------------------------------------------------------
# Existing answer quality functions (reused from original script)
# ---------------------------------------------------------------------------

def build_subject_totals(
    rows_by_question: dict[tuple[str, str], list[sqlite3.Row]],
) -> dict[str, dict[str, float]]:
    subject_totals: dict[str, defaultdict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    for (subject, _qno), rows in rows_by_question.items():
        for row in rows:
            student_id = _student_key(row)
            if student_id is not None:
                subject_totals[subject][student_id] += float(row["ai_score"])
    return {subject: dict(totals) for subject, totals in subject_totals.items()}


def summarize_question(
    subject: str,
    qno: str,
    rows: list[sqlite3.Row],
    subject_totals: dict[str, float],
) -> dict[str, Any]:
    scores = [float(row["ai_score"]) for row in rows]
    max_score = _clean_number(rows[0]["max_score"]) if rows else 0
    total = len(scores)
    full_mark = sum(1 for score in scores if max_score and score >= float(max_score))
    zero = sum(1 for score in scores if score <= 0)
    blank_records = [
        record for row in rows for record in iter_blank_records(row["ai_raw_response"])
    ]
    blanks = summarize_blanks(blank_records, limit=20)
    avg = round(sum(scores) / total, 2) if total else 0
    discrimination = calculate_discrimination(rows, subject_totals, max_score)
    quality = summarize_question_quality(
        avg=avg,
        max_score=max_score,
        total=total,
        zero=zero,
        blanks=blanks,
        discrimination=discrimination,
    )

    return {
        "subject": subject,
        "qno": qno,
        "maxScore": max_score,
        "total": total,
        "avg": avg,
        "fullMark": full_mark,
        "fullMarkRate": _rate(full_mark, total),
        "zero": zero,
        "zeroRate": _rate(zero, total),
        "scoreDist": score_distribution(scores),
        "blanks": blanks,
        **quality,
    }


def calculate_discrimination(
    rows: list[sqlite3.Row],
    subject_totals: dict[str, float],
    max_score: int | float,
) -> float | None:
    if len(rows) < 30 or not max_score:
        return None

    ranked = []
    for row in rows:
        student_id = _student_key(row)
        if student_id is None or student_id not in subject_totals:
            continue
        score = float(row["ai_score"])
        ranked.append((subject_totals[student_id] - score, score))

    if len(ranked) < 30:
        return None

    ranked.sort(key=lambda item: item[0], reverse=True)
    group_size = max(1, round(len(ranked) * 0.27))
    high_avg = sum(score for _total, score in ranked[:group_size]) / group_size
    low_avg = sum(score for _total, score in ranked[-group_size:]) / group_size
    value = (high_avg - low_avg) / float(max_score)
    return round(max(0, min(1, value)), 2)


def score_distribution(scores: list[float]) -> dict[str, int]:
    counts = Counter(_score_key(score) for score in scores)
    return {
        score: count
        for score, count in sorted(
            counts.items(), key=lambda item: (float(item[0]), item[0])
        )
    }


# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------

def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def publish_report(docs_dir: Path) -> list[Path]:
    """Copy the JSON to frontend/public/ and frontend/dist/ (if exists)."""
    target_dirs = [ROOT / "frontend" / "public"]
    dist_dir = ROOT / "frontend" / "dist"
    if dist_dir.exists():
        target_dirs.append(dist_dir)

    for target_dir in target_dirs:
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(docs_dir / PUBLISH_FILENAME, target_dir / PUBLISH_FILENAME)
    return target_dirs


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _rate(count: int, total: int) -> float:
    return round((count / total) * 100, 1) if total else 0


def _student_key(row: sqlite3.Row) -> str | None:
    try:
        value = row["student_id"]
    except (IndexError, KeyError):
        return None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _score_key(score: float) -> str:
    return str(int(score)) if score.is_integer() else f"{score:.2f}".rstrip("0").rstrip(".")


def _clean_number(value: Any) -> int | float:
    number = float(value or 0)
    return int(number) if number.is_integer() else round(number, 2)


if __name__ == "__main__":
    main()
