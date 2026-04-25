"""AI 阅卷深度分析 — 错因聚合 + 诊断文本生成。"""
import logging
import re
from collections import Counter, defaultdict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.grading.models import GradingResult
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.services.exceptions import NotFoundError

logger = logging.getLogger(__name__)

# V1 关键词分类规则
_ERROR_PATTERNS = [
    (re.compile(r"概念|混淆|误写|误用|错误.*名词|名词.*错误"), "概念混淆"),
    (re.compile(r"计算|运算|数值|算错|算术"), "计算错误"),
    (re.compile(r"步骤|不完整|缺少|缺失|遗漏|不全"), "步骤不完整"),
    (re.compile(r"审题|理解|题意|看错"), "审题不清"),
]


def _classify_error(reason: str) -> str:
    for pattern, label in _ERROR_PATTERNS:
        if pattern.search(reason):
            return label
    return "其他"


WRONG_THRESHOLD = 0.6


async def common_wrong_questions(
    db: AsyncSession, *, exam_id: str, school_id: str,
    subject_id: str | None = None,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
) -> dict:
    """按题聚合错误人数和平均得分率，按错误率降序排列。

    "答错"定义：final_score < max_score × 0.6。
    """
    exam = (await db.execute(
        select(Exam).where(Exam.id == exam_id, Exam.school_id == school_id)
    )).scalar_one_or_none()
    if not exam:
        raise NotFoundError("Exam not found")

    subj_q = select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
    if subject_id:
        subj_q = subj_q.where(Subject.id == subject_id)
    if visible_subject_codes is not None:
        subj_q = subj_q.where(Subject.code.in_(visible_subject_codes))
    subjects = list((await db.execute(subj_q)).scalars().all())
    if not subjects:
        return {"questions": []}

    subj_ids = [s.id for s in subjects]

    stmt = (
        select(
            GradingResult.question_id,
            GradingResult.final_score,
            GradingResult.max_score,
        )
        .join(StudentAnswer, StudentAnswer.id == GradingResult.answer_id)
        .where(
            StudentAnswer.subject_id.in_(subj_ids),
            GradingResult.school_id == school_id,
            GradingResult.final_score.isnot(None),
            GradingResult.max_score > 0,
        )
    )
    if visible_class_ids is not None:
        stmt = stmt.join(Student, Student.id == StudentAnswer.student_id).where(
            Student.class_id.in_(visible_class_ids)
        )

    rows = (await db.execute(stmt)).all()

    q_total: dict[str, int] = defaultdict(int)
    q_wrong: dict[str, int] = defaultdict(int)
    q_score_sum: dict[str, float] = defaultdict(float)
    q_max: dict[str, float] = {}

    for row in rows:
        qid = row.question_id
        q_total[qid] += 1
        q_score_sum[qid] += row.final_score
        q_max[qid] = row.max_score
        if row.final_score < row.max_score * WRONG_THRESHOLD:
            q_wrong[qid] += 1

    q_result = await db.execute(
        select(Question.id, Question.name, Question.question_type, Question.max_score)
        .where(Question.subject_id.in_(subj_ids), Question.school_id == school_id)
    )
    questions_meta = {q.id: {"name": q.name, "type": q.question_type} for q in q_result.all()}

    result = []
    for qid, total in q_total.items():
        meta = questions_meta.get(qid, {"name": qid, "type": "unknown"})
        wrong = q_wrong.get(qid, 0)
        max_s = q_max.get(qid, 0)
        mean_rate = round(q_score_sum[qid] / (total * max_s), 4) if total > 0 and max_s > 0 else 0.0
        result.append({
            "question_id": qid,
            "name": meta["name"],
            "question_type": meta["type"],
            "wrong_count": wrong,
            "total_count": total,
            "wrong_rate": round(wrong / total, 4) if total > 0 else 0.0,
            "mean_score_rate": mean_rate,
        })

    result.sort(key=lambda x: x["wrong_rate"], reverse=True)
    return {"questions": result}


async def question_insights(
    db: AsyncSession, *, exam_id: str, school_id: str,
    subject_id: str | None = None,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
) -> dict:
    """聚合每题的错因分布 + 难度/区分度。"""
    # 验证考试
    exam = (await db.execute(
        select(Exam).where(Exam.id == exam_id, Exam.school_id == school_id)
    )).scalar_one_or_none()
    if not exam:
        raise NotFoundError("Exam not found")

    # 获取科目
    subj_q = select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
    if subject_id:
        subj_q = subj_q.where(Subject.id == subject_id)
    if visible_subject_codes is not None:
        subj_q = subj_q.where(Subject.code.in_(visible_subject_codes))
    subjects = list((await db.execute(subj_q)).scalars().all())
    if not subjects:
        return {"questions": []}

    subj_ids = [s.id for s in subjects]

    # 查询所有 GradingResult（有 ai_raw_response 的）
    stmt = (
        select(
            GradingResult.question_id,
            GradingResult.ai_raw_response,
            GradingResult.final_score,
            GradingResult.max_score,
        )
        .join(StudentAnswer, StudentAnswer.id == GradingResult.answer_id)
        .where(
            StudentAnswer.subject_id.in_(subj_ids),
            GradingResult.school_id == school_id,
            GradingResult.final_score.isnot(None),
        )
    )
    if visible_class_ids is not None:
        stmt = stmt.join(Student, Student.id == StudentAnswer.student_id).where(
            Student.class_id.in_(visible_class_ids)
        )

    rows = (await db.execute(stmt)).all()

    # 按题聚合
    q_scores: dict[str, list[float]] = defaultdict(list)
    q_max: dict[str, float] = {}
    q_errors: dict[str, Counter] = defaultdict(Counter)
    q_total: dict[str, int] = defaultdict(int)

    for row in rows:
        qid = row.question_id
        q_scores[qid].append(row.final_score)
        q_max[qid] = row.max_score
        q_total[qid] += 1

        # 解析 ai_raw_response 提取错因
        raw = row.ai_raw_response
        if not raw or not isinstance(raw, dict):
            continue
        details = raw.get("details", [])
        if isinstance(details, str):
            continue
        for detail in details:
            if not isinstance(detail, dict):
                continue
            for blank in detail.get("blanks", []):
                if not isinstance(blank, dict):
                    continue
                if blank.get("correct") is False and blank.get("reason"):
                    cause = _classify_error(blank["reason"])
                    q_errors[qid][cause] += 1

    # 查询题目元数据
    questions_meta = {}
    q_result = await db.execute(
        select(Question.id, Question.name, Question.question_type, Question.max_score)
        .where(Question.subject_id.in_(subj_ids), Question.school_id == school_id)
    )
    for q in q_result.all():
        questions_meta[q.id] = {"name": q.name, "type": q.question_type, "max_score": q.max_score}

    # 构建结果
    result_questions = []
    for qid, scores in q_scores.items():
        meta = questions_meta.get(qid, {"name": qid, "type": "unknown", "max_score": 0})
        max_s = q_max.get(qid, meta["max_score"])
        avg = sum(scores) / len(scores) if scores else 0
        score_rate = round(avg / max_s, 4) if max_s > 0 else 0.0
        total = q_total[qid]

        # 难度和区分度
        difficulty = score_rate
        discrimination = None
        if len(scores) >= 10:
            sorted_s = sorted(scores, reverse=True)
            n27 = max(1, len(sorted_s) * 27 // 100)
            top_avg = sum(sorted_s[:n27]) / n27
            bot_avg = sum(sorted_s[-n27:]) / n27
            discrimination = round((top_avg - bot_avg) / max_s, 4) if max_s > 0 else None

        # 错因分布
        errors = q_errors.get(qid, Counter())
        error_total = sum(errors.values())
        error_causes = []
        for cause, count in errors.most_common():
            error_causes.append({
                "cause": cause,
                "count": count,
                "pct": round(count / total, 4) if total > 0 else 0,
            })

        result_questions.append({
            "question_id": qid,
            "name": meta["name"],
            "question_type": meta["type"],
            "score_rate": score_rate,
            "graded_count": total,
            "error_causes": error_causes,
            "difficulty": difficulty,
            "discrimination": discrimination,
        })

    result_questions.sort(key=lambda x: x["score_rate"])
    return {"questions": result_questions}


async def exam_diagnosis(
    db: AsyncSession, *, exam_id: str, school_id: str,
    subject_id: str | None = None,
    class_id: str | None = None,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
) -> dict:
    """生成考试诊断文本（模板拼接，不调 LLM）。ORC-007。

    F001 修复：所有数据源使用同一 scoped_class_ids 口径。
    当传入 class_id 时，class_avg 来自该班数据，grade_avg 来自全校可见数据。
    两个 summary 调用使用不同 scope 以实现"班级 vs 年级"对比。
    """
    from edu_cloud.modules.analytics.service import exam_summary

    if class_id:
        if visible_class_ids is not None and class_id not in visible_class_ids:
            return {"summary_text": "暂无诊断数据。", "weak_questions": [], "error_distribution": {}, "suggestions": []}
        scoped_class_ids = [class_id]
    else:
        scoped_class_ids = visible_class_ids

    # 班级/当前范围的均分
    summary = await exam_summary(
        db, exam_id=exam_id, school_id=school_id,
        visible_subject_codes=visible_subject_codes,
        visible_class_ids=scoped_class_ids,
    )

    # 年级均分（全可见范围，用于对比基线）
    grade_summary = await exam_summary(
        db, exam_id=exam_id, school_id=school_id,
        visible_subject_codes=visible_subject_codes,
        visible_class_ids=visible_class_ids,
    ) if class_id else summary

    insights = await question_insights(
        db, exam_id=exam_id, school_id=school_id,
        subject_id=subject_id,
        visible_subject_codes=visible_subject_codes,
        visible_class_ids=scoped_class_ids,
    )

    # 构建诊断文本
    parts = []
    subjects = summary.get("subjects", [])
    grade_subjects = grade_summary.get("subjects", [])
    if subjects:
        # F003 修复：subject_id 指定时严格按科目过滤，miss 则跳过均分对比
        if subject_id:
            matched = [s for s in subjects if s.get("subject_id") == subject_id]
            subj = matched[0] if matched else None
        else:
            subj = subjects[0]
        if subj is not None:
            class_avg = subj.get("avg_score")
            grade_avg = None
            if grade_subjects:
                grade_subj = next((g for g in grade_subjects if g.get("subject_id") == subj.get("subject_id")), grade_subjects[0])
                grade_avg = grade_subj.get("avg_score")
            if class_avg is not None and grade_avg is not None:
                diff = round(class_avg - grade_avg, 1)
                if diff < 0:
                    parts.append(f"本次考试均分 {class_avg}，低于年级均分 {abs(diff)} 分。")
                elif diff > 0:
                    parts.append(f"本次考试均分 {class_avg}，高于年级均分 {diff} 分。")
                else:
                    parts.append(f"本次考试均分 {class_avg}，与年级持平。")

    # 薄弱题
    weak = [q for q in insights.get("questions", []) if q["score_rate"] < 0.5]
    weak.sort(key=lambda x: x["score_rate"])
    weak_questions = []
    if weak:
        q = weak[0]
        parts.append(f"主要失分集中在第 {q['name']} 题（得分率 {q['score_rate']:.0%}）。")
        weak_questions = [{"name": w["name"], "score_rate": w["score_rate"]} for w in weak[:5]]

    # 高频错因
    all_errors: Counter = Counter()
    for q in insights.get("questions", []):
        for ec in q.get("error_causes", []):
            all_errors[ec["cause"]] += ec["count"]
    error_distribution = {}
    total_errors = sum(all_errors.values())
    if total_errors > 0:
        top_cause = all_errors.most_common(1)[0]
        pct = top_cause[1] / total_errors
        parts.append(f"{pct:.0%} 的错误为{top_cause[0]}。")
        for cause, cnt in all_errors.most_common():
            error_distribution[cause] = round(cnt / total_errors, 4)

    suggestions = []
    if weak:
        suggestions.append(f"建议重点讲解第 {weak[0]['name']} 题相关知识点。")

    return {
        "summary_text": "".join(parts) if parts else "暂无诊断数据。",
        "weak_questions": weak_questions,
        "error_distribution": error_distribution,
        "suggestions": suggestions,
    }


async def student_ai_diagnosis(
    db: AsyncSession, *, student_id: str, school_id: str,
    exam_id: str | None = None,
    subject_code: str | None = None,
) -> dict:
    """学生个体 AI 诊断文本（模板拼接）。ORC-007。

    F004 修复：
    1. exam_id 用于过滤 last_exam_id，subject_code 过滤知识点关联科目
    2. 接入 StudentErrorPattern 维度
    3. 端点改挂 profile router（见 Step 3 路由修改）
    """
    from edu_cloud.modules.profile.models import StudentKnowledgeMastery, StudentErrorPattern

    # 查询知识点掌握度
    stmt = select(StudentKnowledgeMastery).where(
        StudentKnowledgeMastery.student_id == student_id,
        StudentKnowledgeMastery.school_id == school_id,
    )
    if exam_id:
        stmt = stmt.where(StudentKnowledgeMastery.last_exam_id == exam_id)
    rows = list((await db.execute(stmt)).scalars().all())

    # 查询错误模式
    ep_stmt = select(StudentErrorPattern).where(
        StudentErrorPattern.student_id == student_id,
        StudentErrorPattern.school_id == school_id,
    )
    if subject_code:
        ep_stmt = ep_stmt.where(StudentErrorPattern.subject_code == subject_code)
    error_patterns = list((await db.execute(ep_stmt)).scalars().all())

    improving = []
    declining = []
    weak_points = []

    for m in rows:
        item = {
            "kp_name": m.knowledge_point_id,
            "mastery_level": round(m.mastery_level, 4) if m.mastery_level else 0,
            "trend": m.trend or "stable",
            "recent_scores": m.recent_scores or [],
        }
        if m.trend == "improving":
            improving.append(item)
        elif m.trend == "declining":
            declining.append(item)
        if m.mastery_level is not None and m.mastery_level < 0.6:
            weak_points.append(item)

    # 构建诊断文本
    parts = []
    if declining:
        d = declining[0]
        parts.append(f"知识点'{d['kp_name']}'掌握率持续下降（当前 {d['mastery_level']:.0%}），建议重点关注。")
    if improving:
        imp = improving[0]
        parts.append(f"知识点'{imp['kp_name']}'掌握率在上升（当前 {imp['mastery_level']:.0%}），继续保持。")
    if weak_points and not declining:
        w = weak_points[0]
        parts.append(f"知识点'{w['kp_name']}'掌握率较低（{w['mastery_level']:.0%}），建议加强练习。")

    # F004: 融入错误模式
    if error_patterns:
        ep = error_patterns[0]
        dist = ep.error_distribution or {}
        if dist:
            top_error = max(dist, key=dist.get)
            parts.append(f"主要错误类型为{top_error}（占比 {dist[top_error]:.0%}）。")

    if not parts:
        parts.append("暂无足够数据生成诊断。")

    return {
        "summary": "".join(parts),
        "improving": improving[:5],
        "declining": declining[:5],
        "weak_points": weak_points[:5],
        "error_patterns": [{"subject_code": ep.subject_code, "distribution": ep.error_distribution} for ep in error_patterns[:3]],
    }
