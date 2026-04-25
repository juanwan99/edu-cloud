"""考后预计算管线 — 填充 ClassAnalysis / StudentAnalysis / StudentKnpMastery。

触发：考试发布后由 run_full_pipeline 调用。
幂等：按 UniqueConstraint upsert（merge），重跑覆盖而非重复。
"""
import logging
import math
from collections import defaultdict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.exam.models import Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingResult
from edu_cloud.modules.student.models import Student
from edu_cloud.modules.knowledge.models import QuestionKnowledgePoint
from edu_cloud.modules.analytics.models import ClassAnalysis, StudentAnalysis, StudentKnpMastery

logger = logging.getLogger(__name__)

PASS_THRESHOLD = 0.6
EXCELLENT_THRESHOLD = 0.85
WEAK_KNP_THRESHOLD = 0.6
DISTRIBUTION_BUCKETS = 10


async def compute_exam_analysis(db: AsyncSession, *, exam_id: str, school_id: str) -> dict:
    """填充三张分析表，返回各表写入行数。"""
    subjects = (await db.execute(
        select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
    )).scalars().all()
    if not subjects:
        return {"class_analysis": 0, "student_analysis": 0, "student_knp_mastery": 0}

    subject_ids = [s.id for s in subjects]

    questions_by_subject = await _load_questions(db, subject_ids, school_id)
    scores = await _load_effective_scores(db, exam_id, subject_ids, school_id)
    student_class_map = await _load_student_classes(db, scores.keys())
    kp_links = await _load_kp_links(db, questions_by_subject)

    ca_count = await _compute_class_analysis(
        db, exam_id, school_id, subjects, questions_by_subject, scores, student_class_map,
    )
    sa_count = await _compute_student_analysis(
        db, exam_id, school_id, subjects, questions_by_subject, scores, student_class_map, kp_links,
    )
    knp_count = await _compute_knp_mastery(
        db, exam_id, school_id, scores, student_class_map, kp_links,
    )

    await db.commit()
    logger.info("compute_exam_analysis: exam=%s, class=%d, student=%d, knp=%d",
                exam_id, ca_count, sa_count, knp_count)
    return {"class_analysis": ca_count, "student_analysis": sa_count, "student_knp_mastery": knp_count}


async def _load_questions(
    db: AsyncSession, subject_ids: list[str], school_id: str,
) -> dict[str, dict[str, Question]]:
    result = await db.execute(
        select(Question).where(Question.subject_id.in_(subject_ids), Question.school_id == school_id)
    )
    by_subject: dict[str, dict[str, Question]] = defaultdict(dict)
    for q in result.scalars().all():
        by_subject[q.subject_id][q.id] = q
    return dict(by_subject)


async def _load_effective_scores(
    db: AsyncSession, exam_id: str, subject_ids: list[str], school_id: str,
) -> dict[str, list[dict]]:
    """Returns {student_id: [{subject_id, question_id, score, max_score}, ...]}."""
    # GradingResult.final_score 优先（AI 阅卷），fallback StudentAnswer.score（直接录入）
    effective_score = func.coalesce(GradingResult.final_score, StudentAnswer.score)
    stmt = (
        select(
            StudentAnswer.student_id,
            StudentAnswer.subject_id,
            StudentAnswer.question_id,
            effective_score.label("effective_score"),
            Question.max_score,
        )
        .outerjoin(GradingResult, GradingResult.answer_id == StudentAnswer.id)
        .join(Question, Question.id == StudentAnswer.question_id)
        .where(
            StudentAnswer.exam_id == exam_id,
            StudentAnswer.subject_id.in_(subject_ids),
            StudentAnswer.school_id == school_id,
        )
    )
    rows = (await db.execute(stmt)).all()

    by_student: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row.effective_score is None:
            continue
        by_student[row.student_id].append({
            "subject_id": row.subject_id,
            "question_id": row.question_id,
            "score": float(row.effective_score),
            "max_score": float(row.max_score),
        })
    return dict(by_student)


async def _load_student_classes(
    db: AsyncSession, student_ids,
) -> dict[str, str | None]:
    ids = list(student_ids)
    if not ids:
        return {}
    result = await db.execute(select(Student.id, Student.class_id).where(Student.id.in_(ids)))
    return {r.id: r.class_id for r in result.all()}


async def _load_kp_links(
    db: AsyncSession, questions_by_subject: dict[str, dict[str, Question]],
) -> dict[str, list[str]]:
    """Returns {question_id: [kp_id, ...]}."""
    all_q_ids = [qid for qs in questions_by_subject.values() for qid in qs]
    if not all_q_ids:
        return {}
    result = await db.execute(
        select(QuestionKnowledgePoint.question_id, QuestionKnowledgePoint.knowledge_point_id)
        .where(QuestionKnowledgePoint.question_id.in_(all_q_ids))
    )
    links: dict[str, list[str]] = defaultdict(list)
    for r in result.all():
        links[r.question_id].append(r.knowledge_point_id)
    return dict(links)


async def _compute_class_analysis(
    db: AsyncSession,
    exam_id: str,
    school_id: str,
    subjects: list,
    questions_by_subject: dict,
    scores: dict[str, list[dict]],
    student_class_map: dict[str, str | None],
) -> int:
    count = 0
    for subj in subjects:
        full_score = sum(q.max_score for q in questions_by_subject.get(subj.id, {}).values())
        if full_score <= 0:
            continue

        class_students: dict[str, list[tuple[str, float]]] = defaultdict(list)
        class_question_scores: dict[str, dict[str, list[tuple[float, float]]]] = defaultdict(lambda: defaultdict(list))
        class_kp_scores: dict[str, dict[str, list[tuple[float, float]]]] = defaultdict(lambda: defaultdict(list))

        for stu_id, all_scores in scores.items():
            cls_id = student_class_map.get(stu_id)
            if not cls_id:
                continue
            subj_total = sum(s["score"] for s in all_scores if s["subject_id"] == subj.id)
            subj_items = [s for s in all_scores if s["subject_id"] == subj.id]
            if not subj_items:
                continue
            class_students[cls_id].append((stu_id, subj_total))

            for item in subj_items:
                class_question_scores[cls_id][item["question_id"]].append(
                    (item["score"], item["max_score"])
                )

        for cls_id, stu_scores in class_students.items():
            totals = [t for _, t in stu_scores]
            n = len(totals)
            avg = sum(totals) / n
            pass_count = sum(1 for t in totals if t >= full_score * PASS_THRESHOLD)
            excellent_count = sum(1 for t in totals if t >= full_score * EXCELLENT_THRESHOLD)

            dist = _build_distribution(totals, full_score)

            q_scores = class_question_scores[cls_id]
            wrong_questions = _build_common_wrong_questions(
                q_scores, questions_by_subject.get(subj.id, {}),
            )

            existing = (await db.execute(
                select(ClassAnalysis).where(
                    ClassAnalysis.exam_id == exam_id,
                    ClassAnalysis.subject_id == subj.id,
                    ClassAnalysis.class_id == cls_id,
                )
            )).scalar_one_or_none()

            values = dict(
                school_id=school_id,
                avg_score=round(avg, 2),
                max_score=max(totals),
                min_score=min(totals),
                pass_rate=round(pass_count / n * 100, 2),
                excellent_rate=round(excellent_count / n * 100, 2),
                student_count=n,
                score_distribution=dist,
                common_wrong_questions=wrong_questions,
                knowledge_mastery=None,
            )

            if existing:
                for k, v in values.items():
                    setattr(existing, k, v)
            else:
                ca = ClassAnalysis(
                    exam_id=exam_id, subject_id=subj.id, class_id=cls_id, **values,
                )
                db.add(ca)
            count += 1

    await db.flush()
    return count


def _build_distribution(totals: list[float], full_score: float) -> list[dict]:
    step = full_score / DISTRIBUTION_BUCKETS
    buckets = []
    for i in range(DISTRIBUTION_BUCKETS):
        lo = round(step * i, 2)
        hi = round(step * (i + 1), 2)
        cnt = sum(1 for t in totals if lo <= t < hi) if i < DISTRIBUTION_BUCKETS - 1 else \
              sum(1 for t in totals if lo <= t <= hi)
        buckets.append({"lower": lo, "upper": hi, "count": cnt})
    return buckets


def _build_common_wrong_questions(
    q_scores: dict[str, list[tuple[float, float]]],
    questions: dict[str, Question],
) -> list[dict]:
    entries = []
    for qid, pairs in q_scores.items():
        q = questions.get(qid)
        if not q:
            continue
        n = len(pairs)
        total_score = sum(s for s, _ in pairs)
        total_max = sum(m for _, m in pairs)
        avg_rate = total_score / total_max if total_max > 0 else 1.0
        error_rate = round(1 - avg_rate, 4)
        entries.append({
            "question_id": qid,
            "question_name": q.name,
            "error_rate": error_rate,
            "avg_score_rate": round(avg_rate, 4),
            "avg_score": round(total_score / n, 2),
            "max_score": q.max_score,
        })
    entries.sort(key=lambda e: e["error_rate"], reverse=True)
    return entries[:10]


async def _compute_student_analysis(
    db: AsyncSession,
    exam_id: str,
    school_id: str,
    subjects: list,
    questions_by_subject: dict,
    scores: dict[str, list[dict]],
    student_class_map: dict[str, str | None],
    kp_links: dict[str, list[str]],
) -> int:
    student_subject_totals: dict[str, dict[str, float]] = defaultdict(dict)
    student_totals: dict[str, float] = {}

    for stu_id, all_scores in scores.items():
        total = 0.0
        for subj_id in {s["subject_id"] for s in all_scores}:
            subj_sum = sum(s["score"] for s in all_scores if s["subject_id"] == subj_id)
            student_subject_totals[stu_id][subj_id] = subj_sum
            total += subj_sum
        student_totals[stu_id] = total

    # Grade ranking (同分同名次跳号)
    sorted_grade = sorted(student_totals.items(), key=lambda x: x[1], reverse=True)
    grade_ranks = _rank_with_skip(sorted_grade)

    # Class ranking
    class_groups: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for stu_id, total in student_totals.items():
        cls_id = student_class_map.get(stu_id)
        if cls_id:
            class_groups[cls_id].append((stu_id, total))

    class_ranks: dict[str, int] = {}
    for cls_id, members in class_groups.items():
        sorted_cls = sorted(members, key=lambda x: x[1], reverse=True)
        cls_rank_map = _rank_with_skip(sorted_cls)
        class_ranks.update(cls_rank_map)

    # Weak knowledge per student
    student_weak_kps = _compute_weak_kps(scores, kp_links)

    count = 0
    for stu_id, total in student_totals.items():
        existing = (await db.execute(
            select(StudentAnalysis).where(
                StudentAnalysis.student_id == stu_id,
                StudentAnalysis.exam_id == exam_id,
            )
        )).scalar_one_or_none()

        values = dict(
            school_id=school_id,
            total_score=round(total, 2),
            rank_in_grade=grade_ranks.get(stu_id),
            rank_in_class=class_ranks.get(stu_id),
            subject_scores=student_subject_totals.get(stu_id, {}),
            weak_knowledge=student_weak_kps.get(stu_id, []),
            improvement_trend=None,
        )

        if existing:
            for k, v in values.items():
                setattr(existing, k, v)
        else:
            sa = StudentAnalysis(
                student_id=stu_id, exam_id=exam_id, **values,
            )
            db.add(sa)
        count += 1

    await db.flush()
    return count


def _rank_with_skip(sorted_pairs: list[tuple[str, float]]) -> dict[str, int]:
    """同分同名次，下一名跳号。"""
    ranks: dict[str, int] = {}
    prev_score = None
    prev_rank = 0
    for i, (stu_id, score) in enumerate(sorted_pairs):
        if score != prev_score:
            prev_rank = i + 1
            prev_score = score
        ranks[stu_id] = prev_rank
    return ranks


def _compute_weak_kps(
    scores: dict[str, list[dict]],
    kp_links: dict[str, list[str]],
) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for stu_id, all_scores in scores.items():
        kp_agg: dict[str, dict] = defaultdict(lambda: {"score": 0.0, "max": 0.0})
        for item in all_scores:
            for kp_id in kp_links.get(item["question_id"], []):
                kp_agg[kp_id]["score"] += item["score"]
                kp_agg[kp_id]["max"] += item["max_score"]

        weak = []
        for kp_id, d in kp_agg.items():
            rate = d["score"] / d["max"] if d["max"] > 0 else 0
            if rate < WEAK_KNP_THRESHOLD:
                weak.append({"knp_id": kp_id, "mastery_rate": round(rate, 4)})
        if weak:
            weak.sort(key=lambda x: x["mastery_rate"])
            result[stu_id] = weak
    return result


async def _compute_knp_mastery(
    db: AsyncSession,
    exam_id: str,
    school_id: str,
    scores: dict[str, list[dict]],
    student_class_map: dict[str, str | None],
    kp_links: dict[str, list[str]],
) -> int:
    # Per student×KP aggregation
    stu_kp: dict[tuple[str, str], dict] = defaultdict(lambda: {"score": 0.0, "max": 0.0})
    for stu_id, all_scores in scores.items():
        for item in all_scores:
            for kp_id in kp_links.get(item["question_id"], []):
                key = (stu_id, kp_id)
                stu_kp[key]["score"] += item["score"]
                stu_kp[key]["max"] += item["max_score"]

    # Class-level KP averages
    class_kp_rates: dict[tuple[str, str], list[float]] = defaultdict(list)
    # Grade-level KP averages
    grade_kp_rates: dict[str, list[float]] = defaultdict(list)

    for (stu_id, kp_id), d in stu_kp.items():
        rate = d["score"] / d["max"] if d["max"] > 0 else 0
        cls_id = student_class_map.get(stu_id)
        if cls_id:
            class_kp_rates[(cls_id, kp_id)].append(rate)
        grade_kp_rates[kp_id].append(rate)

    count = 0
    for (stu_id, kp_id), d in stu_kp.items():
        stu_rate = d["score"] / d["max"] if d["max"] > 0 else 0
        cls_id = student_class_map.get(stu_id)
        cls_rates = class_kp_rates.get((cls_id, kp_id), []) if cls_id else []
        cls_rate = sum(cls_rates) / len(cls_rates) if cls_rates else 0
        grd_rates = grade_kp_rates.get(kp_id, [])
        grd_rate = sum(grd_rates) / len(grd_rates) if grd_rates else 0

        existing = (await db.execute(
            select(StudentKnpMastery).where(
                StudentKnpMastery.student_id == stu_id,
                StudentKnpMastery.exam_id == exam_id,
                StudentKnpMastery.knp_id == kp_id,
            )
        )).scalar_one_or_none()

        values = dict(
            school_id=school_id,
            stu_rate=round(stu_rate, 3),
            class_rate=round(cls_rate, 3),
            grade_rate=round(grd_rate, 3),
        )

        if existing:
            for k, v in values.items():
                setattr(existing, k, v)
        else:
            m = StudentKnpMastery(
                student_id=stu_id, exam_id=exam_id, knp_id=kp_id, **values,
            )
            db.add(m)
        count += 1

    await db.flush()
    return count
