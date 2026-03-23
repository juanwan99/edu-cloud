import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.exam.models import Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.marking.models import MarkingScore

logger = logging.getLogger(__name__)


async def get_subjects_with_progress(
    db: AsyncSession, exam_id: str, school_id: str,
) -> list[dict]:
    """获取考试下所有科目及题目的阅卷进度。"""
    subjects = (await db.execute(
        select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
    )).scalars().all()

    result = []
    for subj in subjects:
        questions = (await db.execute(
            select(Question).where(Question.subject_id == subj.id)
        )).scalars().all()

        q_list = []
        for q in questions:
            total = (await db.execute(
                select(func.count()).select_from(StudentAnswer).where(
                    StudentAnswer.question_id == q.id,
                )
            )).scalar() or 0

            graded = (await db.execute(
                select(func.count()).select_from(MarkingScore).where(
                    MarkingScore.question_id == q.id,
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
) -> dict | None:
    """获取该题下一个未批改的学生答卷。"""
    graded_ids_q = select(MarkingScore.answer_id).where(
        MarkingScore.question_id == question_id,
    )

    answer = (await db.execute(
        select(StudentAnswer).where(
            StudentAnswer.question_id == question_id,
            StudentAnswer.id.not_in(graded_ids_q),
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
        select(func.count()).select_from(MarkingScore).where(
            MarkingScore.question_id == question_id,
        )
    )).scalar() or 0

    return {
        "answer_id": answer.id,
        "student_id": answer.student_id,
        "image_path": answer.image_path,
        "position": {"current": graded + 1, "total": total},
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
) -> MarkingScore:
    """保存教师评分。"""
    ms = MarkingScore(
        answer_id=answer_id,
        question_id=question_id,
        marker_id=marker_id,
        school_id=school_id,
        score=score,
        max_score=max_score,
        comment=comment,
    )
    db.add(ms)
    await db.commit()
    return ms


async def get_progress(db: AsyncSession, exam_id: str, school_id: str) -> dict:
    """获取考试的整体阅卷进度。"""
    subjects_data = await get_subjects_with_progress(db, exam_id, school_id)

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
