from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.services.analytics_workflow import GradingResult
from edu_cloud.services.analytics_workflow import StudentAnswer
from edu_cloud.services.analytics_workflow import Student


async def convert_level_score(
    db: AsyncSession,
    school_id: str,
    exam_id: str,
    subject_id: str,
    levels: list[dict],
    class_id: str | None = None,
) -> dict | None:
    effective_score = func.coalesce(GradingResult.final_score, StudentAnswer.score)
    stmt = (
        select(
            Student.id.label("student_id"),
            Student.name,
            func.sum(effective_score).label("total_score"),
        )
        .join(StudentAnswer, StudentAnswer.student_id == Student.id)
        .outerjoin(GradingResult, GradingResult.answer_id == StudentAnswer.id)
        .where(StudentAnswer.exam_id == exam_id)
        .where(StudentAnswer.subject_id == subject_id)
        .where(StudentAnswer.school_id == school_id)
        .where(effective_score.is_not(None))
        .group_by(Student.id, Student.name)
        .order_by(func.sum(effective_score).desc())
    )
    if class_id:
        stmt = stmt.where(Student.class_id == class_id)

    rows = (await db.execute(stmt)).all()
    if not rows:
        return None

    total = len(rows)
    sorted_levels = sorted(levels, key=lambda lv: lv["start_pct"])

    students_out = []
    level_buckets: dict[str, list] = {lv["level"]: [] for lv in sorted_levels}

    # ORC-005: tied scores must be in same level — group by score, use same percentile
    score_groups = []
    current_score = None
    for rank_idx, row in enumerate(rows):
        if row.total_score != current_score:
            current_score = row.total_score
            score_groups.append({"score": current_score, "start_idx": rank_idx, "students": []})
        score_groups[-1]["students"].append(row)

    for group in score_groups:
        pct = (group["start_idx"] / total) * 100
        assigned_level = sorted_levels[-1]
        for lv in sorted_levels:
            if lv["start_pct"] <= pct < lv["end_pct"]:
                assigned_level = lv
                break

        for row in group["students"]:
            entry = {
                "student_id": row.student_id,
                "name": row.name,
                "raw_score": row.total_score,
                "level": assigned_level["level"],
                "rank": group["start_idx"] + 1,
                "assigned_score": 0.0,
            }
            level_buckets[assigned_level["level"]].append(entry)
            students_out.append(entry)

    for lv in sorted_levels:
        bucket = level_buckets[lv["level"]]
        n = len(bucket)
        for i, stu in enumerate(bucket):
            if n <= 1:
                stu["assigned_score"] = round((lv["score_min"] + lv["score_max"]) / 2, 1)
            else:
                stu["assigned_score"] = round(
                    lv["score_max"] - (lv["score_max"] - lv["score_min"]) * i / (n - 1), 1
                )

    level_stats = []
    for lv in sorted_levels:
        bucket = level_buckets[lv["level"]]
        raw_scores = [s["raw_score"] for s in bucket]
        count = len(bucket)
        level_stats.append({
            "level": lv["level"],
            "count": count,
            "pct": round(count / total * 100, 1) if total else 0,
            "raw_min": min(raw_scores) if raw_scores else None,
            "raw_max": max(raw_scores) if raw_scores else None,
            "assigned_range": [lv["score_min"], lv["score_max"]],
        })

    def _build_dist(score_list, bins=10):
        if not score_list:
            return {"segments": [], "counts": []}
        lo, hi = min(score_list), max(score_list)
        step = max((hi - lo) / bins, 1)
        segments, counts = [], []
        for i in range(bins):
            seg_lo = lo + step * i
            seg_hi = lo + step * (i + 1)
            segments.append(f"{seg_lo:.0f}-{seg_hi:.0f}")
            if i == bins - 1:
                cnt = sum(1 for s in score_list if seg_lo <= s <= seg_hi)
            else:
                cnt = sum(1 for s in score_list if seg_lo <= s < seg_hi)
            counts.append(cnt)
        return {"segments": segments, "counts": counts}

    return {
        "total_students": total,
        "level_stats": level_stats,
        "students": students_out,
        "distribution_before": _build_dist([r.total_score for r in rows]),
        "distribution_after": _build_dist([s["assigned_score"] for s in students_out]),
    }
