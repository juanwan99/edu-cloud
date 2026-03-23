import csv
import io
import logging
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.exam.models import Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.marking.models import MarkingScore

logger = logging.getLogger(__name__)


async def export_scores_csv(
    db: AsyncSession, exam_id: str, school_id: str,
) -> str:
    """导出考试成绩为 CSV 字符串。

    列: 学生ID, 科目1_题1, 科目1_题2, ..., 科目1_总分, ..., 总分
    """
    subjects = (await db.execute(
        select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
        .order_by(Subject.name)
    )).scalars().all()

    columns = ["学生ID"]
    question_order = []  # [(subject_name, question_id)]
    subject_boundaries = []  # [(subject_name, start_idx, end_idx)]

    for subj in subjects:
        questions = (await db.execute(
            select(Question).where(Question.subject_id == subj.id)
            .order_by(Question.name)
        )).scalars().all()

        start_idx = len(question_order)
        for q in questions:
            columns.append(f"{subj.name}_{q.name}")
            question_order.append((subj.name, q.id))
        end_idx = len(question_order)

        columns.append(f"{subj.name}_总分")
        subject_boundaries.append((subj.name, start_idx, end_idx))

    columns.append("总分")

    # 获取所有评分
    scores = (await db.execute(
        select(
            StudentAnswer.student_id,
            MarkingScore.question_id,
            MarkingScore.score,
        )
        .join(MarkingScore, MarkingScore.answer_id == StudentAnswer.id)
        .where(StudentAnswer.exam_id == exam_id)
    )).all()

    student_scores = defaultdict(dict)
    for student_id, question_id, score in scores:
        student_scores[student_id][question_id] = score

    all_students = (await db.execute(
        select(StudentAnswer.student_id).where(
            StudentAnswer.exam_id == exam_id,
        ).distinct().order_by(StudentAnswer.student_id)
    )).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)

    for student_id in all_students:
        row = [student_id]
        total = 0.0
        s_map = student_scores.get(student_id, {})

        for subj_name, start_idx, end_idx in subject_boundaries:
            subject_total = 0.0
            for i in range(start_idx, end_idx):
                _, q_id = question_order[i]
                s = s_map.get(q_id)
                if s is not None:
                    row.append(round(s, 1))
                    subject_total += s
                    total += s
                else:
                    row.append("")
            row.append(round(subject_total, 1))

        row.append(round(total, 1))
        writer.writerow(row)

    return output.getvalue()
