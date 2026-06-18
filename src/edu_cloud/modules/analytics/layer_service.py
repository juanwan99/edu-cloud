"""分层学情分析：按得分率将学生分为优秀/良好/待提升三层，统计每层 KP 掌握率。"""
import logging
from collections import defaultdict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.analytics.models import StudentKnpMastery
from edu_cloud.modules.analytics.segment_service import get_segment_config
from edu_cloud.modules.analytics.service import (
    _verify_exam, _get_subjects, _get_max_by_subject,
)
from edu_cloud.services.effective_scores import get_effective_scores_batch

logger = logging.getLogger(__name__)

DEFAULT_LAYER_BOUNDARIES = [85, 60]
DEFAULT_LAYER_LABELS = ["优秀", "良好", "待提升"]


async def layer_analysis(
    db: AsyncSession, *, exam_id: str, school_id: str,
    subject_id: str | None = None,
    class_id: str | None = None,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
) -> dict:
    # Narrow class scope when class_id is specified
    if class_id:
        if visible_class_ids is not None and class_id not in visible_class_ids:
            return {"exam_id": exam_id, "layers": [], "maxDiffKnowledges": []}
        effective_class_ids = [class_id]
    else:
        effective_class_ids = visible_class_ids

    await _verify_exam(db, exam_id, school_id)
    subjects = await _get_subjects(db, exam_id, school_id, visible_subject_codes, subject_id)
    subj_ids = [s.id for s in subjects]
    if not subj_ids:
        return {"exam_id": exam_id, "layers": [], "maxDiffKnowledges": []}

    max_by_subject = await _get_max_by_subject(db, subj_ids, school_id)
    total_max = sum(max_by_subject.get(s.id, 0.0) for s in subjects)

    scores_by_subject = await get_effective_scores_batch(db, subj_ids, school_id, effective_class_ids)
    student_totals: dict[str, float] = defaultdict(float)
    for subj in subjects:
        for s in scores_by_subject.get(subj.id, []):
            student_totals[s["student_id"]] += s["effective_score"]

    if not student_totals or total_max <= 0:
        return {"exam_id": exam_id, "layers": [], "maxDiffKnowledges": []}

    boundaries = DEFAULT_LAYER_BOUNDARIES
    labels = DEFAULT_LAYER_LABELS

    student_layers: dict[str, str] = {}
    for sid, score in student_totals.items():
        rate_pct = score / total_max * 100
        if rate_pct >= boundaries[0]:
            student_layers[sid] = labels[0]
        elif rate_pct >= boundaries[1]:
            student_layers[sid] = labels[1]
        else:
            student_layers[sid] = labels[2]

    layer_students: dict[str, list[str]] = defaultdict(list)
    layer_scores: dict[str, list[float]] = defaultdict(list)
    for sid, label in student_layers.items():
        layer_students[label].append(sid)
        layer_scores[label].append(student_totals[sid])

    layers = []
    for label in labels:
        sids = layer_students.get(label, [])
        scores = layer_scores.get(label, [])
        count = len(sids)
        if count > 0:
            avg_rate = round(sum(scores) / count / total_max, 4)
        else:
            avg_rate = None
        layers.append({
            "label": label,
            "count": count,
            "avgScoreRate": avg_rate,
        })

    knp_result = await db.execute(
        select(StudentKnpMastery).where(
            StudentKnpMastery.exam_id == exam_id,
            StudentKnpMastery.school_id == school_id,
        )
    )
    knp_rows = knp_result.scalars().all()

    layer_knp_rates: dict[str, dict[str, list[float]]] = {label: defaultdict(list) for label in labels}
    for row in knp_rows:
        label = student_layers.get(row.student_id)
        if label and row.stu_rate is not None:
            layer_knp_rates[label][row.concept_id].append(float(row.stu_rate))

    for layer in layers:
        knp_data = layer_knp_rates.get(layer["label"], {})
        kp_mastery = []
        for kp_id, rates in knp_data.items():
            kp_mastery.append({
                "knpId": kp_id,
                "avgRate": round(sum(rates) / len(rates), 4),
            })
        layer["knowledgeMastery"] = kp_mastery

    max_diff = _compute_max_diff_knowledges(labels, layer_knp_rates)

    return {
        "exam_id": exam_id,
        "layers": layers,
        "maxDiffKnowledges": max_diff,
    }


def _compute_max_diff_knowledges(
    labels: list[str],
    layer_knp_rates: dict[str, dict[str, list[float]]],
    top_n: int = 5,
) -> list[dict]:
    if len(labels) < 2:
        return []

    top_label = labels[0]
    bottom_label = labels[-1]
    top_knps = layer_knp_rates.get(top_label, {})
    bottom_knps = layer_knp_rates.get(bottom_label, {})

    all_kp_ids = set(top_knps.keys()) | set(bottom_knps.keys())
    diffs = []
    for kp_id in all_kp_ids:
        top_rates = top_knps.get(kp_id, [])
        bottom_rates = bottom_knps.get(kp_id, [])
        top_avg = sum(top_rates) / len(top_rates) if top_rates else 0
        bottom_avg = sum(bottom_rates) / len(bottom_rates) if bottom_rates else 0
        diff = abs(top_avg - bottom_avg)
        diffs.append({
            "knpId": kp_id,
            "topLayerRate": round(top_avg, 4),
            "bottomLayerRate": round(bottom_avg, 4),
            "diff": round(diff, 4),
        })

    diffs.sort(key=lambda x: x["diff"], reverse=True)
    return diffs[:top_n]
