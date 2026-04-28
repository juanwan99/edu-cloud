"""人工阅卷/校对服务层 — 读写统一 GradingResult 表。

同一条 GradingResult 可能来自：
  - AI 先评（status=ai_done, ai_score 有值）— 教师校对修改 final_score/source
  - 纯人工（status=ai_pending 或 无记录）— 教师首次评分，直接落 confirmed
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.exam.models import Subject, Question
from edu_cloud.modules.grading.models import GradingAssignment, GradingResult
from edu_cloud.modules.scan.models import StudentAnswer

logger = logging.getLogger(__name__)


def _build_ai_info(gr) -> dict | None:
    """从 GradingResult 构建完整的 ai 信息（details/deductions/comment/recognizedText）。"""
    if gr.ai_score is None:
        return None

    from edu_cloud.modules.grading.detail_flatten import flatten_llm_details, parse_raw_content

    ai_raw = gr.ai_raw_response if isinstance(gr.ai_raw_response, dict) else {}
    details = ai_raw.get("details")
    deductions = ai_raw.get("deductions") or []
    comment = ai_raw.get("comment", "")
    recognized_text = ai_raw.get("recognizedText")

    if not details or not deductions or not comment:
        parsed = parse_raw_content(ai_raw.get("raw_content", ""))
        if parsed:
            if not details:
                details = parsed.get("details")
            if not deductions:
                deductions = parsed.get("deductions") or []
            if not comment:
                comment = parsed.get("comment", "")
            if not recognized_text:
                recognized_text = parsed.get("llmRecognizedText", "")

    details = flatten_llm_details(details)

    return {
        "score": gr.ai_score,
        "confidence": gr.ai_confidence,
        "feedback": gr.ai_feedback,
        "result_id": gr.id,
        "details": details,
        "deductions": deductions,
        "comment": comment,
        "recognizedText": recognized_text,
    }


async def get_subjects_with_progress(
    db: AsyncSession,
    exam_id: str,
    school_id: str,
    visible_codes: list[str] | None = None,
) -> list[dict]:
    """获取考试下所有科目及题目的阅卷进度。

    "已批改" = GradingResult.status == 'confirmed' 的答卷数。
    """
    stmt = select(Subject).where(
        Subject.exam_id == exam_id, Subject.school_id == school_id
    )
    if visible_codes is not None:
        if not visible_codes:
            return []
        stmt = stmt.where(Subject.code.in_(visible_codes))
    subjects = (await db.execute(stmt)).scalars().all()

    result = []
    for subj in subjects:
        questions = (await db.execute(
            select(Question).where(
                Question.subject_id == subj.id,
                Question.question_type.notin_(["choice", "multi_choice"]),
            )
        )).scalars().all()

        q_list = []
        for q in questions:
            total = (await db.execute(
                select(func.count()).select_from(StudentAnswer).where(
                    StudentAnswer.question_id == q.id,
                )
            )).scalar() or 0

            graded = (await db.execute(
                select(func.count()).select_from(GradingResult).where(
                    GradingResult.question_id == q.id,
                    GradingResult.status == "confirmed",
                )
            )).scalar() or 0

            q_list.append({
                "id": q.id, "name": q.name, "max_score": q.max_score,
                "total_answers": total, "graded_count": graded,
            })

        result.append({"id": subj.id, "name": subj.name, "questions": q_list})
    return result


async def get_next_answer(
    db: AsyncSession, question_id: str, school_id: str,
    *, teacher_id: str | None = None,
    mode: str = "ungraded",
) -> dict | None:
    """获取该题下一份答卷 + AI 预测（若存在）。

    mode:
      - "ungraded": 未 confirmed 的答卷（默认，人工阅卷流程）
      - "ai_review": AI 已评(ai_done)但未确认的答卷（复核流程）

    返回结构：
    {
      answer_id, student_id, image_path,
      position: {current, total},
      ai: None 或 {score, confidence, feedback, result_id}
      max_score: float
    }
    """
    if mode == "ai_review":
        # 复核模式：取 AI 已评但未人工确认的答卷
        ai_done_q = (await db.execute(
            select(GradingResult).where(
                GradingResult.question_id == question_id,
                GradingResult.school_id == school_id,
                GradingResult.status == "ai_done",
            ).order_by(GradingResult.created_at)
            .limit(1)
        )).scalar_one_or_none()

        if not ai_done_q:
            return None

        answer = (await db.execute(
            select(StudentAnswer).where(
                StudentAnswer.id == ai_done_q.answer_id,
                StudentAnswer.school_id == school_id,
            )
        )).scalar_one_or_none()
        if not answer:
            return None

        # 统计：AI 已阅总数 / 已复核数
        ai_total = (await db.execute(
            select(func.count()).select_from(GradingResult).where(
                GradingResult.question_id == question_id,
                GradingResult.school_id == school_id,
                GradingResult.ai_score.is_not(None),
            )
        )).scalar() or 0

        ai_reviewed = (await db.execute(
            select(func.count()).select_from(GradingResult).where(
                GradingResult.question_id == question_id,
                GradingResult.school_id == school_id,
                GradingResult.ai_score.is_not(None),
                GradingResult.status == "confirmed",
            )
        )).scalar() or 0

        q = (await db.execute(
            select(Question).where(Question.id == question_id)
        )).scalar_one_or_none()
        max_score = q.max_score if q else 0.0

        return {
            "answer_id": answer.id,
            "student_id": answer.student_id,
            "image_path": answer.image_path,
            "position": {"current": ai_reviewed + 1, "total": ai_total},
            "ai": _build_ai_info(ai_done_q),
            "max_score": max_score,
            "is_anomaly": answer.is_anomaly,
            "anomaly_type": answer.anomaly_type,
        }

    # ---- 默认 ungraded 模式 ----

    # 配额检查：教师改到 total_count 就停
    if teacher_id:
        my_assigns = (await db.execute(
            select(GradingAssignment).where(
                GradingAssignment.assigned_to == teacher_id,
                GradingAssignment.school_id == school_id,
                GradingAssignment.is_second_grading.is_(False),
            )
        )).scalars().all()
        for a in my_assigns:
            if question_id in (a.question_ids or []):
                if a.total_count > 0 and a.graded_count >= a.total_count:
                    return None
                break

    # 查已 confirmed 的 answer_id 集
    confirmed_ids_q = select(GradingResult.answer_id).where(
        GradingResult.question_id == question_id,
        GradingResult.status == "confirmed",
    )

    answer = (await db.execute(
        select(StudentAnswer).where(
            StudentAnswer.question_id == question_id,
            StudentAnswer.id.not_in(confirmed_ids_q),
        ).order_by(StudentAnswer.student_id)
        .limit(1)
    )).scalar_one_or_none()

    if not answer:
        return None

    total = (await db.execute(
        select(func.count()).select_from(StudentAnswer).where(
            StudentAnswer.question_id == question_id,
        )
    )).scalar() or 0

    graded = (await db.execute(
        select(func.count()).select_from(GradingResult).where(
            GradingResult.question_id == question_id,
            GradingResult.status == "confirmed",
        )
    )).scalar() or 0

    # AI 预测（如果已有 ai_done 记录）
    ai_row = (await db.execute(
        select(GradingResult).where(GradingResult.answer_id == answer.id)
    )).scalar_one_or_none()

    ai_info = _build_ai_info(ai_row) if ai_row else None

    # 查题目满分
    q = (await db.execute(
        select(Question).where(Question.id == question_id)
    )).scalar_one_or_none()
    max_score = q.max_score if q else 0.0

    return {
        "answer_id": answer.id,
        "student_id": answer.student_id,
        "image_path": answer.image_path,
        "position": {"current": graded + 1, "total": total},
        "ai": ai_info,
        "max_score": max_score,
        "is_anomaly": answer.is_anomaly,
        "anomaly_type": answer.anomaly_type,
    }


async def get_answer_at(
    db: AsyncSession, question_id: str, school_id: str, offset: int,
) -> dict | None:
    """按索引获取某题的第 offset 份答卷（0-based），包含已有评分。"""
    total = (await db.execute(
        select(func.count()).select_from(StudentAnswer).where(
            StudentAnswer.question_id == question_id,
            StudentAnswer.school_id == school_id,
        )
    )).scalar() or 0

    if offset < 0 or offset >= total:
        return None

    answer = (await db.execute(
        select(StudentAnswer).where(
            StudentAnswer.question_id == question_id,
            StudentAnswer.school_id == school_id,
        ).order_by(StudentAnswer.student_id)
        .offset(offset).limit(1)
    )).scalar_one_or_none()

    if not answer:
        return None

    gr = (await db.execute(
        select(GradingResult).where(GradingResult.answer_id == answer.id)
    )).scalar_one_or_none()

    ai_info = None
    graded_score = None
    graded_comment = None
    if gr:
        ai_info = _build_ai_info(gr)
        if gr.status == "confirmed":
            graded_score = gr.final_score
            graded_comment = gr.review_comment

    q = (await db.execute(
        select(Question).where(Question.id == question_id)
    )).scalar_one_or_none()
    max_score = q.max_score if q else 0.0

    return {
        "answer_id": answer.id,
        "student_id": answer.student_id,
        "image_path": answer.image_path,
        "position": {"current": offset + 1, "total": total},
        "ai": ai_info,
        "max_score": max_score,
        "is_anomaly": answer.is_anomaly,
        "anomaly_type": answer.anomaly_type,
        "graded_score": graded_score,
        "graded_comment": graded_comment,
    }


async def submit_score(
    db: AsyncSession,
    answer_id: str,
    question_id: str,
    marker_id: str,
    school_id: str,
    score: float,
    max_score: float,
    comment: str | None = None,
) -> GradingResult:
    """落盘教师评分到 GradingResult（upsert 语义）。

    - 若已有 GradingResult（AI 预评）：改 final_score+status+source+reviewer_id
    - 若无：新建 source='manual', status='confirmed'
    - 若已 confirmed：抛 ValueError（调用方转 409）
    """
    existing = (await db.execute(
        select(GradingResult).where(GradingResult.answer_id == answer_id)
    )).scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if existing:
        if existing.status == "confirmed":
            raise ValueError("该答卷已评分")
        # AI 预评 → 教师校对：判断 approve 还是 override
        if existing.ai_score is not None and abs((existing.ai_score or 0) - score) < 1e-6:
            existing.source = "ai"
        else:
            existing.source = "ai_override" if existing.ai_score is not None else "manual"
        existing.final_score = score
        existing.status = "confirmed"
        existing.reviewer_id = marker_id
        existing.reviewed_at = now
        existing.review_comment = comment
        existing.version = existing.version + 1
        await db.commit()
        await db.refresh(existing)
        return existing

    gr = GradingResult(
        answer_id=answer_id,
        question_id=question_id,
        school_id=school_id,
        final_score=score,
        max_score=max_score,
        status="confirmed",
        source="manual",
        reviewer_id=marker_id,
        reviewed_at=now,
        review_comment=comment,
    )
    db.add(gr)
    await db.commit()
    await db.refresh(gr)
    return gr


async def update_assignment_progress(
    db: AsyncSession, question_id: str, teacher_id: str, school_id: str,
) -> None:
    """提交评分后递增教师对应 assignment 的 graded_count。"""
    assignments = (await db.execute(
        select(GradingAssignment).where(
            GradingAssignment.assigned_to == teacher_id,
            GradingAssignment.school_id == school_id,
        )
    )).scalars().all()
    for a in assignments:
        if question_id in (a.question_ids or []):
            a.graded_count = a.graded_count + 1
            if a.total_count > 0 and a.graded_count >= a.total_count:
                a.status = "completed"
            elif a.status == "pending":
                a.status = "in_progress"
    await db.flush()


async def get_progress(
    db: AsyncSession,
    exam_id: str,
    school_id: str,
    visible_codes: list[str] | None = None,
) -> dict:
    """获取考试的整体阅卷进度。"""
    subjects_data = await get_subjects_with_progress(
        db, exam_id, school_id, visible_codes=visible_codes,
    )

    overall_total = 0
    overall_graded = 0
    for subj in subjects_data:
        for q in subj["questions"]:
            overall_total += q["total_answers"]
            overall_graded += q["graded_count"]

    return {
        "subjects": subjects_data,
        "overall": {
            "total": overall_total,
            "graded": overall_graded,
            "percentage": round(overall_graded / overall_total * 100, 1) if overall_total > 0 else 0,
        },
    }
