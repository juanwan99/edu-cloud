"""AI grading report service.

This report is intentionally separate from traditional score analysis. It
focuses on AI coverage, confidence, AI-vs-final score deltas, OCR/pipeline
quality, question-level error causes, and actionable watchlists.
"""
from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.analytics.identity import resolve_student_identities
from edu_cloud.modules.analytics.insights_service import _classify_error
from edu_cloud.services.analytics_workflow import Exam, Question, Subject
from edu_cloud.services.analytics_workflow import GradingPipelineLog, GradingResult
from edu_cloud.services.analytics_workflow import QuestionKnowledgePoint
from edu_cloud.services.analytics_workflow import StudentAnswer
from edu_cloud.services.exceptions import NotFoundError

LOW_CONFIDENCE_THRESHOLD = 0.6
SQL_IN_CHUNK_SIZE = 900


def _chunks(items: list[str], size: int = SQL_IN_CHUNK_SIZE):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _effective_score(row) -> float | None:
    if row.final_score is not None:
        return float(row.final_score)
    if row.scan_score is not None:
        return float(row.scan_score)
    return None


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def _extract_error_causes(raw_response) -> Counter:
    causes: Counter = Counter()
    if not isinstance(raw_response, dict):
        return causes
    details = raw_response.get("details", [])
    if not isinstance(details, list):
        return causes
    for detail in details:
        if not isinstance(detail, dict):
            continue
        blanks = detail.get("blanks", [])
        if not isinstance(blanks, list):
            continue
        for blank in blanks:
            if not isinstance(blank, dict):
                continue
            if blank.get("correct") is False and blank.get("reason"):
                causes[_classify_error(str(blank["reason"]))] += 1
    return causes


async def _load_subjects(
    db: AsyncSession,
    *,
    exam_id: str,
    school_id: str,
    subject_id: str | None,
    visible_subject_codes: list[str] | None,
) -> list[Subject]:
    stmt = select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
    if subject_id:
        stmt = stmt.where(Subject.id == subject_id)
    if visible_subject_codes is not None:
        stmt = stmt.where(Subject.code.in_(visible_subject_codes))
    return list((await db.execute(stmt)).scalars().all())


async def build_ai_grading_report(
    db: AsyncSession,
    *,
    exam_id: str,
    school_id: str,
    subject_id: str | None = None,
    class_id: str | None = None,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
) -> dict:
    exam = (await db.execute(
        select(Exam).where(Exam.id == exam_id, Exam.school_id == school_id)
    )).scalar_one_or_none()
    if not exam:
        raise NotFoundError("Exam not found")

    if class_id and visible_class_ids is not None and class_id not in visible_class_ids:
        return _empty_report(exam_id)

    effective_class_ids = [class_id] if class_id else visible_class_ids
    visible_set = set(effective_class_ids) if effective_class_ids is not None else None

    subjects = await _load_subjects(
        db,
        exam_id=exam_id,
        school_id=school_id,
        subject_id=subject_id,
        visible_subject_codes=visible_subject_codes,
    )
    subject_ids = [s.id for s in subjects]
    subject_by_id = {s.id: s for s in subjects}
    if not subject_ids:
        return _empty_report(exam_id)

    stmt = (
        select(
            StudentAnswer.id.label("answer_id"),
            StudentAnswer.student_id,
            StudentAnswer.subject_id,
            StudentAnswer.question_id,
            StudentAnswer.score.label("scan_score"),
            StudentAnswer.detected_answer,
            StudentAnswer.is_anomaly,
            StudentAnswer.anomaly_type,
            StudentAnswer.question_type.label("answer_question_type"),
            Question.name.label("question_name"),
            Question.question_type,
            Question.max_score,
            GradingResult.ai_score,
            GradingResult.ai_confidence,
            GradingResult.ai_feedback,
            GradingResult.ai_raw_response,
            GradingResult.final_score,
            GradingResult.status.label("grading_status"),
            GradingResult.source.label("grading_source"),
        )
        .select_from(StudentAnswer)
        .join(Question, Question.id == StudentAnswer.question_id)
        .outerjoin(GradingResult, GradingResult.answer_id == StudentAnswer.id)
        .where(
            StudentAnswer.exam_id == exam_id,
            StudentAnswer.subject_id.in_(subject_ids),
            StudentAnswer.school_id == school_id,
            StudentAnswer.is_absent.is_(False),
        )
    )
    rows = list((await db.execute(stmt)).all())
    identities = await resolve_student_identities(
        db, school_id=school_id, raw_student_ids=[row.student_id for row in rows],
    )

    scoped_rows = []
    unmatched_raw_ids: set[str] = set()
    for row in rows:
        identity = identities.get(row.student_id)
        if not identity or identity.canonical_student_id is None:
            unmatched_raw_ids.add(row.student_id)
            canonical_student_id = row.student_id
            class_value = None
        else:
            canonical_student_id = identity.canonical_student_id
            class_value = identity.class_id
        if visible_set is not None and class_value not in visible_set:
            continue
        scoped_rows.append((row, identity, canonical_student_id, class_value))

    answer_ids = [row.answer_id for row, *_ in scoped_rows]
    pipeline = await _pipeline_section(db, answer_ids)
    question_diagnostics = _question_diagnostics(scoped_rows, subject_by_id)
    student_watchlist = _student_watchlist(scoped_rows)
    teaching_actions = _teaching_actions(question_diagnostics, student_watchlist)

    coverage = _coverage_section(scoped_rows)
    confidence = _confidence_section(scoped_rows)
    quality = _quality_section(scoped_rows)
    warnings = await _data_warnings(db, subject_ids, unmatched_raw_ids)

    return {
        "exam_id": exam_id,
        "subject_id": subject_id,
        "class_id": class_id,
        "coverage": coverage,
        "confidence": confidence,
        "quality": quality,
        "ocr_pipeline": pipeline,
        "question_diagnostics": question_diagnostics,
        "student_watchlist": student_watchlist,
        "teaching_actions": teaching_actions,
        "data_warnings": warnings,
    }


def _empty_report(exam_id: str) -> dict:
    return {
        "exam_id": exam_id,
        "coverage": {
            "answer_count": 0,
            "matched_student_count": 0,
            "ai_scored_count": 0,
            "confirmed_count": 0,
            "pending_review_count": 0,
        },
        "confidence": {"avg_confidence": None, "low_confidence_count": 0},
        "quality": {"ai_human_delta_count": 0, "avg_abs_delta": None, "override_count": 0},
        "ocr_pipeline": {"log_count": 0, "error_count": 0, "blank_count": 0},
        "question_diagnostics": [],
        "student_watchlist": [],
        "teaching_actions": [],
        "data_warnings": [],
    }


def _coverage_section(scoped_rows: list[tuple]) -> dict:
    answer_count = len(scoped_rows)
    matched_students = {
        canonical_id for _, identity, canonical_id, _ in scoped_rows
        if identity and identity.canonical_student_id
    }
    ai_scored = [row for row, *_ in scoped_rows if row.grading_source in ("ai", "ai_override")]
    confirmed = [row for row, *_ in scoped_rows if row.grading_status == "confirmed"]
    pending_review = [
        row for row, *_ in scoped_rows
        if row.grading_status == "ai_done"
    ]
    final_scores = [row for row, *_ in scoped_rows if _effective_score(row) is not None]
    objective = [
        row for row, *_ in scoped_rows
        if (row.question_type or row.answer_question_type) == "choice"
    ]
    subjective = [
        row for row, *_ in scoped_rows
        if (row.question_type or row.answer_question_type) != "choice"
    ]
    return {
        "answer_count": answer_count,
        "matched_student_count": len(matched_students),
        "objective_answer_count": len(objective),
        "subjective_answer_count": len(subjective),
        "ai_scored_count": len(ai_scored),
        "ai_coverage_rate": round(len(ai_scored) / len(subjective), 4) if subjective else 0,
        "confirmed_count": len(confirmed),
        "pending_review_count": len(pending_review),
        "final_score_count": len(final_scores),
    }


def _confidence_section(scoped_rows: list[tuple]) -> dict:
    values = [
        float(row.ai_confidence)
        for row, *_ in scoped_rows
        if row.grading_source in ("ai", "ai_override") and row.ai_confidence is not None
    ]
    low = [v for v in values if v < LOW_CONFIDENCE_THRESHOLD]
    buckets = {
        "high": sum(1 for v in values if v >= 0.8),
        "medium": sum(1 for v in values if 0.6 <= v < 0.8),
        "low": len(low),
    }
    return {
        "avg_confidence": _avg(values),
        "low_confidence_count": len(low),
        "threshold": LOW_CONFIDENCE_THRESHOLD,
        "buckets": buckets,
    }


def _quality_section(scoped_rows: list[tuple]) -> dict:
    deltas = []
    large_delta_by_question: dict[str, dict] = {}
    for row, *_ in scoped_rows:
        if row.grading_source not in ("ai", "ai_override") or row.final_score is None:
            continue
        delta = float(row.final_score) - float(row.ai_score)
        abs_delta = abs(delta)
        deltas.append(abs_delta)
        if abs_delta > 0:
            q = large_delta_by_question.setdefault(
                row.question_id,
                {
                    "question_id": row.question_id,
                    "question_name": row.question_name,
                    "count": 0,
                    "total_abs_delta": 0.0,
                    "max_abs_delta": 0.0,
                },
            )
            q["count"] += 1
            q["total_abs_delta"] += abs_delta
            q["max_abs_delta"] = max(q["max_abs_delta"], abs_delta)

    question_delta = []
    for q in large_delta_by_question.values():
        question_delta.append({
            **q,
            "avg_abs_delta": round(q["total_abs_delta"] / q["count"], 4),
        })
    question_delta.sort(key=lambda item: (-item["avg_abs_delta"], item["question_name"]))

    return {
        "ai_human_delta_count": len(deltas),
        "avg_abs_delta": _avg(deltas),
        "max_abs_delta": round(max(deltas), 4) if deltas else None,
        "override_count": sum(1 for d in deltas if d > 0),
        "override_rate": round(sum(1 for d in deltas if d > 0) / len(deltas), 4) if deltas else 0,
        "question_delta_top": question_delta[:10],
    }


async def _pipeline_section(db: AsyncSession, answer_ids: list[str]) -> dict:
    if not answer_ids:
        return {"log_count": 0, "error_count": 0, "blank_count": 0, "avg_total_ms": None}
    logs = []
    for batch in _chunks(answer_ids):
        result = await db.execute(
            select(GradingPipelineLog).where(GradingPipelineLog.answer_id.in_(batch))
        )
        logs.extend(result.scalars().all())
    total_ms = [float(log.total_ms) for log in logs if log.total_ms is not None]
    confidence = [float(log.confidence) for log in logs if log.confidence is not None]
    error_types = Counter(log.error_type for log in logs if log.error_type)
    return {
        "log_count": len(logs),
        "error_count": sum(1 for log in logs if log.error_type),
        "blank_count": sum(1 for log in logs if log.is_blank),
        "avg_total_ms": _avg(total_ms),
        "avg_confidence": _avg(confidence),
        "error_types": [
            {"type": key, "count": count}
            for key, count in error_types.most_common()
        ],
    }


def _question_diagnostics(scoped_rows: list[tuple], subject_by_id: dict[str, Subject]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for row, *_ in scoped_rows:
        q = grouped.setdefault(
            row.question_id,
            {
                "question_id": row.question_id,
                "question_name": row.question_name,
                "subject_id": row.subject_id,
                "subject_name": subject_by_id.get(row.subject_id).name if subject_by_id.get(row.subject_id) else None,
                "question_type": row.question_type or row.answer_question_type,
                "answer_count": 0,
                "scores": [],
                "max_score": float(row.max_score or 0),
                "ai_confidences": [],
                "deltas": [],
                "error_counter": Counter(),
            },
        )
        q["answer_count"] += 1
        score = _effective_score(row)
        if score is not None:
            q["scores"].append(score)
        if row.ai_confidence is not None:
            q["ai_confidences"].append(float(row.ai_confidence))
        if row.ai_score is not None and row.final_score is not None:
            q["deltas"].append(abs(float(row.final_score) - float(row.ai_score)))
        q["error_counter"].update(_extract_error_causes(row.ai_raw_response))

    diagnostics = []
    for q in grouped.values():
        avg_score = _avg(q["scores"]) or 0
        max_score = q["max_score"]
        error_total = sum(q["error_counter"].values())
        diagnostics.append({
            "question_id": q["question_id"],
            "question_name": q["question_name"],
            "subject_id": q["subject_id"],
            "subject_name": q["subject_name"],
            "question_type": q["question_type"],
            "answer_count": q["answer_count"],
            "avg_score": round(avg_score, 4),
            "max_score": max_score,
            "score_rate": round(avg_score / max_score, 4) if max_score > 0 else 0,
            "avg_ai_confidence": _avg(q["ai_confidences"]),
            "low_confidence_count": sum(
                1 for value in q["ai_confidences"] if value < LOW_CONFIDENCE_THRESHOLD
            ),
            "avg_abs_delta": _avg(q["deltas"]),
            "error_causes": [
                {
                    "cause": cause,
                    "count": count,
                    "pct": round(count / error_total, 4) if error_total else 0,
                }
                for cause, count in q["error_counter"].most_common()
            ],
        })
    diagnostics.sort(key=lambda item: (item["score_rate"], -item["low_confidence_count"]))
    return diagnostics


def _student_watchlist(scoped_rows: list[tuple]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for row, identity, canonical_id, class_id in scoped_rows:
        student = grouped.setdefault(
            canonical_id,
            {
                "student_id": canonical_id,
                "student_name": identity.name if identity else None,
                "student_number": identity.student_number if identity else None,
                "class_id": class_id,
                "score": 0.0,
                "max_score": 0.0,
                "low_confidence_count": 0,
                "pending_review_count": 0,
                "anomaly_count": 0,
            },
        )
        score = _effective_score(row)
        if score is not None:
            student["score"] += score
            student["max_score"] += float(row.max_score or 0)
        if row.ai_confidence is not None and float(row.ai_confidence) < LOW_CONFIDENCE_THRESHOLD:
            student["low_confidence_count"] += 1
        if row.grading_status == "ai_done":
            student["pending_review_count"] += 1
        if row.is_anomaly:
            student["anomaly_count"] += 1

    watchlist = []
    for student in grouped.values():
        score_rate = (
            round(student["score"] / student["max_score"], 4)
            if student["max_score"] > 0 else None
        )
        if (
            (score_rate is not None and score_rate < 0.6)
            or student["low_confidence_count"]
            or student["pending_review_count"]
            or student["anomaly_count"]
        ):
            watchlist.append({
                **student,
                "score": round(student["score"], 2),
                "max_score": round(student["max_score"], 2),
                "score_rate": score_rate,
            })
    watchlist.sort(key=lambda item: (
        item["score_rate"] if item["score_rate"] is not None else 99,
        -item["low_confidence_count"],
        -item["pending_review_count"],
    ))
    return watchlist[:50]


def _teaching_actions(question_diagnostics: list[dict], student_watchlist: list[dict]) -> list[dict]:
    actions = []
    weak_questions = [q for q in question_diagnostics if q["score_rate"] < 0.6]
    if weak_questions:
        q = weak_questions[0]
        actions.append({
            "type": "question_review",
            "priority": "high",
            "title": f"优先讲评第 {q['question_name']} 题",
            "evidence": {
                "score_rate": q["score_rate"],
                "low_confidence_count": q["low_confidence_count"],
                "top_error_cause": q["error_causes"][0]["cause"] if q["error_causes"] else None,
            },
        })
    if student_watchlist:
        actions.append({
            "type": "student_intervention",
            "priority": "medium",
            "title": "优先处理低分或待复核学生",
            "evidence": {"student_count": len(student_watchlist)},
        })
    if question_diagnostics and not actions:
        q = question_diagnostics[0]
        actions.append({
            "type": "quality_review",
            "priority": "medium",
            "title": f"复核第 {q['question_name']} 题 AI 诊断样本",
            "evidence": {
                "score_rate": q["score_rate"],
                "low_confidence_count": q["low_confidence_count"],
            },
        })
    return actions


async def _data_warnings(
    db: AsyncSession,
    subject_ids: list[str],
    unmatched_raw_ids: set[str],
) -> list[dict]:
    warnings = []
    if unmatched_raw_ids:
        warnings.append({
            "type": "unmatched_student_ids",
            "count": len(unmatched_raw_ids),
            "samples": sorted(unmatched_raw_ids)[:20],
        })
    kp_count = (
        await db.execute(
            select(QuestionKnowledgePoint.question_id)
            .join(Question, Question.id == QuestionKnowledgePoint.question_id)
            .where(Question.subject_id.in_(subject_ids))
            .limit(1)
        )
    ).first()
    if not kp_count:
        warnings.append({
            "type": "missing_knowledge_links",
            "message": "题目暂未绑定知识点，知识点诊断不可用。",
        })
    return warnings
