"""考后题库/错题本制品应用服务（模块外）。

将考试完成后写入 bank 模块的两类制品——题库条目 `BankQuestion` 与学生错题本
`StudentErrorBook`——的生成逻辑，以及错误模式聚合所需的错题本读模型，从 pipeline
模块上移到模块外服务边界，使 pipeline 不再直接 import `edu_cloud.modules.bank`，
拆掉 `pipeline -> bank` 依赖边（D-03H）。pipeline 仍是考后冷数据流水线的 owner，
本服务只负责承载 bank 制品的读写。

对外契约保持不变：
- `populate_bank_questions` / `populate_error_books` 经 pipeline.service re-export，
  既有调用点（pipeline `run_full_pipeline`、exam `publish_service`、exam_import、
  编排服务 `services.exam_publish_pipeline`）与测试 patch（`pipeline.service.*`
  命名空间）行为零变更。
- 有效分沿用冷数据 owner 权威规则 `services.post_exam_cold_data._get_effective_score`
  （调用期局部 import，避免 services 层导入期耦合，与 `services.post_exam_adaptive`
  同范式；冷数据 owner 已上移模块外 services，D-03I）。
- 错误模式聚合（`pipeline.service.update_error_patterns`）经
  `list_error_book_students_for_subject` / `list_error_book_entries_for_student`
  两个读模型获取错题本数据，聚合与落库（`profile.StudentErrorPattern`）仍归 pipeline。
"""
import logging
from collections import Counter

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def populate_bank_questions(db: AsyncSession, *, exam_id: str, school_id: str) -> int:
    """将考试的题目自动入库到 BankQuestion。返回新增数量。

    模块内符号采用调用期局部 import：避免 services 层导入期耦合 modules。
    """
    from edu_cloud.modules.exam.models import Subject, Question
    from edu_cloud.modules.bank.models import BankQuestion

    subjects = await db.execute(
        select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
    )
    subject_ids = [s.id for s in subjects.scalars().all()]
    if not subject_ids:
        return 0

    questions = await db.execute(
        select(Question).where(Question.subject_id.in_(subject_ids))
    )
    created = 0
    for q in questions.scalars().all():
        stats = await _compute_question_stats(db, question_id=q.id, school_id=school_id)

        bq = BankQuestion(
            school_id=school_id,
            question_type=q.question_type,
            max_score=q.max_score,
            correct_answer=q.correct_answer,
            source_exam_id=exam_id,
            source_question_id=q.id,
            difficulty=stats["difficulty"],
            discrimination=stats["discrimination"],
            sample_count=stats["sample_count"],
            common_errors=stats["common_errors"],
        )
        nested = await db.begin_nested()
        db.add(bq)
        try:
            await nested.commit()
            created += 1
        except IntegrityError:
            await nested.rollback()
            logger.debug("bank_question already exists: question_id=%s", q.id)

    await db.commit()
    logger.info("populate_bank_questions: exam=%s, created=%d", exam_id, created)
    return created


async def populate_error_books(db: AsyncSession, *, exam_id: str, school_id: str) -> int:
    """收集错题到学生错题本。返回新增数量。

    有效分沿用冷数据 owner 权威规则 `services.post_exam_cold_data._get_effective_score`
    （调用期局部 import，避免 services 层导入期耦合）。
    """
    from edu_cloud.modules.exam.models import Question
    from edu_cloud.modules.scan.models import StudentAnswer
    from edu_cloud.modules.grading.models import GradingResult
    from edu_cloud.modules.knowledge.models import QuestionKnowledgePoint
    from edu_cloud.modules.bank.models import BankQuestion, StudentErrorBook
    from edu_cloud.services.post_exam_cold_data import _get_effective_score

    answers = await db.execute(
        select(StudentAnswer, Question)
        .join(Question, Question.id == StudentAnswer.question_id)
        .where(
            StudentAnswer.exam_id == exam_id,
            StudentAnswer.school_id == school_id,
            StudentAnswer.is_absent.is_(False),
        )
    )

    created = 0
    for sa, q in answers.all():
        effective_score = await _get_effective_score(db, answer_id=sa.id)
        if effective_score is None:
            effective_score = sa.score or 0.0

        if effective_score >= q.max_score:
            continue

        gr_result = await db.execute(
            select(GradingResult).where(GradingResult.answer_id == sa.id)
        )
        gr = gr_result.scalar_one_or_none()

        kp_result = await db.execute(
            select(QuestionKnowledgePoint.concept_id)
            .where(QuestionKnowledgePoint.question_id == q.id)
        )
        kp_ids = [row[0] for row in kp_result.all()]

        bq_result = await db.execute(
            select(BankQuestion.id).where(
                BankQuestion.source_question_id == q.id,
                BankQuestion.school_id == school_id,
            )
        )
        bank_q_id = bq_result.scalar_one_or_none()

        eb = StudentErrorBook(
            school_id=school_id,
            student_id=sa.student_id,
            question_id=q.id,
            bank_question_id=bank_q_id,
            exam_id=exam_id,
            student_answer_image=sa.image_path,
            student_score=effective_score,
            max_score=q.max_score,
            correct_answer=q.correct_answer,
            ai_feedback=gr.ai_feedback if gr else None,
            knowledge_point_ids=kp_ids if kp_ids else None,
            mastery_status="unmastered",
            source="auto",
        )
        nested = await db.begin_nested()
        db.add(eb)
        try:
            await nested.commit()
            created += 1
        except IntegrityError:
            await nested.rollback()
            logger.debug("error_book entry already exists: student=%s question=%s", sa.student_id, q.id)

    await db.commit()
    logger.info("populate_error_books: exam=%s, created=%d", exam_id, created)
    return created


async def _compute_question_stats(
    db: AsyncSession, *, question_id: str, school_id: str,
) -> dict:
    from edu_cloud.modules.scan.models import StudentAnswer
    from edu_cloud.modules.exam.models import Question

    answers = await db.execute(
        select(StudentAnswer.score, StudentAnswer.detected_answer)
        .where(
            StudentAnswer.question_id == question_id,
            StudentAnswer.school_id == school_id,
            StudentAnswer.is_absent.is_(False),
        )
    )
    rows = answers.all()
    if not rows:
        return {"difficulty": None, "discrimination": None, "sample_count": 0, "common_errors": None}

    q_result = await db.execute(select(Question.max_score).where(Question.id == question_id))
    max_score = q_result.scalar_one_or_none() or 1.0

    scores = [float(row[0] or 0) for row in rows]
    sample_count = len(scores)
    difficulty = sum(scores) / (sample_count * max_score) if sample_count > 0 else None

    discrimination = None
    if sample_count >= 10:
        sorted_scores = sorted(scores, reverse=True)
        n27 = max(1, int(sample_count * 0.27))
        high_group = sorted_scores[:n27]
        low_group = sorted_scores[-n27:]
        discrimination = (sum(high_group) / (n27 * max_score)) - (sum(low_group) / (n27 * max_score))

    common_errors = None
    detected_answers = [row[1] for row in rows if row[1] is not None]
    if detected_answers:
        counter = Counter(detected_answers)
        total = sum(counter.values())
        common_errors = {k: round(v / total, 3) for k, v in counter.most_common(5)}

    return {
        "difficulty": round(difficulty, 4) if difficulty is not None else None,
        "discrimination": round(discrimination, 4) if discrimination is not None else None,
        "sample_count": sample_count,
        "common_errors": common_errors,
    }


async def list_error_book_students_for_subject(
    db: AsyncSession, *, exam_id: str, school_id: str, subject_id: str,
) -> list[str]:
    """本考试本科目有错题记录的去重学生 id 列表（错题本读模型）。

    供 `pipeline.service.update_error_patterns` 定位受影响学生，避免 pipeline 直接
    import `StudentErrorBook`。
    """
    from edu_cloud.modules.bank.models import StudentErrorBook
    from edu_cloud.modules.exam.models import Question

    rows = await db.execute(
        select(StudentErrorBook.student_id)
        .join(Question, Question.id == StudentErrorBook.question_id)
        .where(
            StudentErrorBook.exam_id == exam_id,
            StudentErrorBook.school_id == school_id,
            Question.subject_id == subject_id,
        )
        .distinct()
    )
    return [row[0] for row in rows.all()]


async def list_error_book_entries_for_student(
    db: AsyncSession, *, student_id: str, school_id: str, subject_code: str,
) -> list[tuple[str | None, str]]:
    """某学生在某科目（按 subject code 跨考试）的错题条目 `(error_type, exam_id)` 明细。

    供 `pipeline.service.update_error_patterns` 聚合错误类型分布与考试覆盖数；聚合与
    落库（`profile.StudentErrorPattern`）仍归 pipeline，本读模型只返回所需字段。
    """
    from edu_cloud.modules.bank.models import StudentErrorBook
    from edu_cloud.modules.exam.models import Question, Subject

    rows = await db.execute(
        select(StudentErrorBook.error_type, StudentErrorBook.exam_id)
        .join(Question, Question.id == StudentErrorBook.question_id)
        .join(Subject, Subject.id == Question.subject_id)
        .where(
            StudentErrorBook.student_id == student_id,
            StudentErrorBook.school_id == school_id,
            Subject.code == subject_code,
        )
    )
    return [(row[0], row[1]) for row in rows.all()]
