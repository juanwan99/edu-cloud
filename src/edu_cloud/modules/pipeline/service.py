"""考试完成后的自动数据生成流水线（从 exam-ai 迁入）。

触发条件：Exam.status → completed
幂等保证：DF-007 — try/except IntegrityError 兜底
有效分数：统一读取 GradingResult.final_score（权威单一源）
"""
import logging
from collections import Counter
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingResult
from edu_cloud.modules.bank.models import BankQuestion, StudentErrorBook
from edu_cloud.modules.knowledge.models import QuestionKnowledgePoint
from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode
from edu_cloud.modules.profile.models import StudentExamSnapshot, StudentKnowledgeMastery, StudentErrorPattern
from edu_cloud.modules.student.models import Student
from edu_cloud.services.student_identity import resolve_student_identities

logger = logging.getLogger(__name__)


async def _get_effective_score(db: AsyncSession, answer_id: str) -> float | None:
    """获取单个答题的最终有效分。

    优先级：GradingResult.final_score（权威单一值）> StudentAnswer.score（客观题自动判分）
    """
    result = await db.execute(
        select(StudentAnswer.score, GradingResult.final_score)
        .outerjoin(GradingResult, GradingResult.answer_id == StudentAnswer.id)
        .where(StudentAnswer.id == answer_id)
    )
    row = result.one_or_none()
    if not row:
        return None
    if row.final_score is not None:
        return row.final_score
    return row.score


async def populate_bank_questions(db: AsyncSession, *, exam_id: str, school_id: str) -> int:
    """将考试的题目自动入库到 BankQuestion。返回新增数量。"""
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
    """收集错题到学生错题本。返回新增数量。"""
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


async def _get_effective_scores_for_subject(
    db: AsyncSession, *, exam_id: str, subject_id: str, school_id: str,
) -> dict[str, list[tuple[str, float, float]]]:
    """本科目每个学生的有效分明细，pipeline 自有局部查询（不依赖 analytics）。

    有效分 = COALESCE(GradingResult.final_score, StudentAnswer.score)，与本模块
    `_get_effective_score` 同一权威规则；inner join Question 限定本科目题目（等价于
    原 valid_question_ids 过滤），跳过缺考与无有效分的答题。

    分组键是 **canonical student id**：扫描数据可能用 UUID（`students.id`）或外部
    条码键（如经验条码）写入 `student_answers.student_id`，同一学生的选择题与主观题
    可能落在不同 raw key。复用模块外共享 resolver `services.student_identity`
    （与 analytics `get_effective_scores` 同一归一化规则）把 raw key 归一到 canonical
    学生，避免同一学生被拆成多个 StudentExamSnapshot（D-03B 回归收口）。
    """
    effective = func.coalesce(GradingResult.final_score, StudentAnswer.score)
    rows = await db.execute(
        select(
            StudentAnswer.student_id,
            StudentAnswer.question_id,
            effective.label("effective_score"),
            Question.max_score,
        )
        .join(Question, Question.id == StudentAnswer.question_id)
        .outerjoin(GradingResult, GradingResult.answer_id == StudentAnswer.id)
        .where(
            StudentAnswer.subject_id == subject_id,
            StudentAnswer.school_id == school_id,
            StudentAnswer.is_absent.is_(False),
            Question.subject_id == subject_id,
            Question.school_id == school_id,
        )
    )

    valid_rows = [row for row in rows.all() if row.effective_score is not None]
    identities = await resolve_student_identities(
        db,
        school_id=school_id,
        raw_student_ids=[row.student_id for row in valid_rows],
    )
    # 与 analytics.get_effective_scores 一致：花名册有匹配时丢弃 unmatched 的 raw key；
    # 整批都匹配不上（如花名册未导入）时回退按 raw key 分组，避免丢失全部数据。
    include_unmatched_rows = not any(
        identity.canonical_student_id for identity in identities.values()
    )

    result: dict[str, list[tuple[str, float, float]]] = {}
    for row in valid_rows:
        identity = identities.get(row.student_id)
        if (not identity or identity.canonical_student_id is None) and not include_unmatched_rows:
            continue
        canonical_student_id = (
            identity.canonical_student_id
            if identity and identity.canonical_student_id
            else row.student_id
        )
        result.setdefault(canonical_student_id, []).append(
            (row.question_id, row.effective_score, row.max_score)
        )
    return result


async def generate_exam_snapshots(db: AsyncSession, *, exam_id: str, school_id: str) -> int:
    subjects = await db.execute(
        select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
    )
    exam_result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam_obj = exam_result.scalar_one_or_none()
    exam_date = exam_obj.created_at if exam_obj else None

    created = 0
    for subj in subjects.scalars().all():
        eff_scores = await _get_effective_scores_for_subject(
            db, exam_id=exam_id, subject_id=subj.id, school_id=school_id,
        )
        if not eff_scores:
            continue

        student_scores = []
        for stu_id, scores_list in eff_scores.items():
            total = sum(s[1] for s in scores_list)
            max_total = sum(s[2] for s in scores_list)
            student_scores.append((stu_id, total, max_total))

        sorted_by_score = sorted(student_scores, key=lambda x: x[1], reverse=True)
        grade_size = len(sorted_by_score)

        student_ids = [s[0] for s in student_scores]
        student_class_map = {}
        if student_ids:
            stu_rows = await db.execute(
                select(Student.id, Student.class_id).where(Student.id.in_(student_ids))
            )
            student_class_map = {r[0]: r[1] for r in stu_rows.all()}

        class_groups: dict[str, list[tuple[str, float]]] = {}
        for stu_id, total, _ in sorted_by_score:
            cls_id = student_class_map.get(stu_id)
            if cls_id:
                class_groups.setdefault(cls_id, []).append((stu_id, total))

        class_rank_map: dict[str, int] = {}
        class_size_map: dict[str, int] = {}
        for cls_id, members in class_groups.items():
            class_size_map[cls_id] = len(members)
            for rank_idx, (stu_id, _) in enumerate(members):
                class_rank_map[stu_id] = rank_idx + 1

        kp_scores_by_student: dict[str, dict] = {}
        q_ids = list({q_id for scores_list in eff_scores.values() for q_id, _, _ in scores_list})
        if q_ids:
            kp_links = await db.execute(
                select(QuestionKnowledgePoint.question_id,
                       ConceptGraphNode.id, ConceptGraphNode.name)
                .join(ConceptGraphNode, ConceptGraphNode.id == QuestionKnowledgePoint.concept_id)
                .where(QuestionKnowledgePoint.question_id.in_(q_ids))
            )
            q_to_kp: dict[str, list[tuple[str, str]]] = {}
            for q_id, concept_id, concept_name in kp_links.all():
                q_to_kp.setdefault(q_id, []).append((concept_id, concept_name))

            for stu_id, scores_list in eff_scores.items():
                kp_agg: dict[str, dict] = {}
                for q_id, eff, max_s in scores_list:
                    for concept_id, concept_name in q_to_kp.get(q_id, []):
                        if concept_id not in kp_agg:
                            kp_agg[concept_id] = {"name": concept_name, "score": 0, "max": 0}
                        kp_agg[concept_id]["score"] += eff
                        kp_agg[concept_id]["max"] += max_s
                for concept_id, d in kp_agg.items():
                    d["score"] = round(d["score"], 2)
                    d["max"] = round(d["max"], 2)
                    d["rate"] = round(d["score"] / d["max"], 4) if d["max"] > 0 else 0
                if kp_agg:
                    kp_scores_by_student[stu_id] = kp_agg

        for grade_rank_idx, (stu_id, total, max_total) in enumerate(sorted_by_score):
            cls_id = student_class_map.get(stu_id)

            existing = await db.execute(
                select(StudentExamSnapshot).where(
                    StudentExamSnapshot.student_id == stu_id,
                    StudentExamSnapshot.exam_id == exam_id,
                    StudentExamSnapshot.subject_code == subj.code,
                    StudentExamSnapshot.school_id == school_id,
                )
            )
            snap = existing.scalar_one_or_none()
            if snap:
                snap.total_score = total
                snap.max_score = max_total
                snap.score_rate = round(total / max_total, 4) if max_total > 0 else 0
                snap.grade_rank = grade_rank_idx + 1
                snap.grade_size = grade_size
                snap.class_rank = class_rank_map.get(stu_id)
                snap.class_size = class_size_map.get(cls_id) if cls_id else None
                snap.knowledge_scores = kp_scores_by_student.get(stu_id)
            else:
                snap = StudentExamSnapshot(
                    school_id=school_id, student_id=stu_id, exam_id=exam_id,
                    subject_code=subj.code, total_score=total, max_score=max_total,
                    score_rate=round(total / max_total, 4) if max_total > 0 else 0,
                    grade_rank=grade_rank_idx + 1, grade_size=grade_size,
                    class_rank=class_rank_map.get(stu_id),
                    class_size=class_size_map.get(cls_id) if cls_id else None,
                    class_id_at_exam=cls_id,
                    knowledge_scores=kp_scores_by_student.get(stu_id),
                    exam_date=exam_date,
                )
                db.add(snap)
            created += 1

    await db.commit()
    logger.info("generate_exam_snapshots: exam=%s, created=%d", exam_id, created)
    return created


async def update_knowledge_mastery(db: AsyncSession, *, exam_id: str, school_id: str) -> int:
    subjects = await db.execute(
        select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
    )
    subject_ids = [s.id for s in subjects.scalars().all()]
    if not subject_ids:
        return 0

    answers = await db.execute(
        select(StudentAnswer, Question, QuestionKnowledgePoint.concept_id)
        .join(Question, Question.id == StudentAnswer.question_id)
        .join(QuestionKnowledgePoint, QuestionKnowledgePoint.question_id == Question.id)
        .where(
            StudentAnswer.exam_id == exam_id,
            StudentAnswer.school_id == school_id,
            StudentAnswer.is_absent.is_(False),
            Question.max_score > 0,
        )
    )

    agg: dict[tuple[str, str], list[float]] = {}
    for sa, q, concept_id in answers.all():
        eff = await _get_effective_score(db, answer_id=sa.id)
        if eff is None:
            eff = sa.score or 0.0
        rate = eff / q.max_score if q.max_score > 0 else 0
        agg.setdefault((sa.student_id, concept_id), []).append(rate)

    updated = 0
    for (stu_id, concept_id), rates in agg.items():
        new_rate = sum(rates) / len(rates) if rates else 0
        cnt = len(rates)

        existing = await db.execute(
            select(StudentKnowledgeMastery).where(
                StudentKnowledgeMastery.student_id == stu_id,
                StudentKnowledgeMastery.concept_id == concept_id,
                StudentKnowledgeMastery.school_id == school_id,
            )
        )
        mastery = existing.scalar_one_or_none()

        if mastery:
            if mastery.last_exam_id == exam_id:
                continue
            old_level = mastery.mastery_level
            mastery.mastery_level = round(0.7 * new_rate + 0.3 * old_level, 4)
            mastery.attempt_count += cnt
            if new_rate >= 0.9:
                mastery.correct_count += cnt
            elif new_rate > 0:
                mastery.partial_count += cnt
            scores = mastery.recent_scores or []
            scores.append(round(new_rate, 4))
            if len(scores) > 5:
                scores = scores[-5:]
            mastery.recent_scores = scores
            if len(scores) >= 3:
                avg_old = sum(scores[:-1]) / len(scores[:-1])
                if new_rate > avg_old + 0.05:
                    mastery.trend = "improving"
                elif new_rate < avg_old - 0.05:
                    mastery.trend = "declining"
                else:
                    mastery.trend = "stable"
            mastery.last_exam_id = exam_id
            mastery.confidence = min(1.0, mastery.attempt_count / 20)
        else:
            mastery = StudentKnowledgeMastery(
                school_id=school_id, student_id=stu_id, concept_id=concept_id,
                mastery_level=round(new_rate, 4), confidence=min(1.0, cnt / 20),
                attempt_count=cnt, correct_count=cnt if new_rate >= 0.9 else 0,
                partial_count=cnt if 0 < new_rate < 0.9 else 0,
                trend="stable", recent_scores=[round(new_rate, 4)], last_exam_id=exam_id,
            )
            db.add(mastery)
        updated += 1

    await db.commit()
    logger.info("update_knowledge_mastery: exam=%s, updated=%d", exam_id, updated)
    return updated


async def update_error_patterns(db: AsyncSession, *, exam_id: str, school_id: str) -> int:
    subjects = await db.execute(
        select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
    )

    updated = 0
    for subj in subjects.scalars().all():
        this_exam_errors = await db.execute(
            select(StudentErrorBook.student_id)
            .join(Question, Question.id == StudentErrorBook.question_id)
            .where(
                StudentErrorBook.exam_id == exam_id,
                StudentErrorBook.school_id == school_id,
                Question.subject_id == subj.id,
            )
            .distinct()
        )
        affected_students = [r[0] for r in this_exam_errors.all()]
        if not affected_students:
            continue

        for stu_id in affected_students:
            all_errors = await db.execute(
                select(StudentErrorBook)
                .join(Question, Question.id == StudentErrorBook.question_id)
                .join(Subject, Subject.id == Question.subject_id)
                .where(
                    StudentErrorBook.student_id == stu_id,
                    StudentErrorBook.school_id == school_id,
                    Subject.code == subj.code,
                )
            )
            error_list = all_errors.scalars().all()
            total_errors = len(error_list)

            type_counts: dict[str, int] = {}
            exam_ids_set: set[str] = set()
            for eb in error_list:
                etype = eb.error_type or "未分类"
                type_counts[etype] = type_counts.get(etype, 0) + 1
                exam_ids_set.add(eb.exam_id)
            distribution = {k: round(v / total_errors, 3) for k, v in type_counts.items()} if total_errors > 0 else {}
            exam_count = len(exam_ids_set)

            existing = await db.execute(
                select(StudentErrorPattern).where(
                    StudentErrorPattern.student_id == stu_id,
                    StudentErrorPattern.subject_code == subj.code,
                    StudentErrorPattern.school_id == school_id,
                )
            )
            pattern = existing.scalar_one_or_none()

            if pattern:
                pattern.total_errors = total_errors
                pattern.exam_count = exam_count
                pattern.error_distribution = distribution
            else:
                pattern = StudentErrorPattern(
                    school_id=school_id, student_id=stu_id, subject_code=subj.code,
                    error_distribution=distribution, total_errors=total_errors, exam_count=exam_count,
                )
                db.add(pattern)
            updated += 1

    await db.commit()
    logger.info("update_error_patterns: exam=%s, updated=%d", exam_id, updated)
    return updated


async def run_full_pipeline(db: AsyncSession, *, exam_id: str, school_id: str) -> dict:
    """完整冷数据流水线：考试完成后一键执行 pipeline 自有的所有数据生成步骤。

    跨模块的考后副作用已移出本模块，由模块外编排服务
    `services.post_exam_pipeline.run_post_exam_pipeline` 串联补齐：
    - analytics 考后预聚合 `exam_analysis`（D-03B）
    - adaptive BKT 掌握度更新 `adaptive_mastery`（D-03E，经
      `services.post_exam_adaptive.update_adaptive_mastery`，pipeline 不再 import adaptive）

    因此 `run_full_pipeline` 只产 pipeline 自有冷数据各步骤，不含 `exam_analysis` /
    `adaptive_mastery`。
    """
    results = {
        "bank_questions": await populate_bank_questions(db, exam_id=exam_id, school_id=school_id),
        "error_books": await populate_error_books(db, exam_id=exam_id, school_id=school_id),
        "exam_snapshots": await generate_exam_snapshots(db, exam_id=exam_id, school_id=school_id),
        "knowledge_mastery": await update_knowledge_mastery(db, exam_id=exam_id, school_id=school_id),
        "error_patterns": await update_error_patterns(db, exam_id=exam_id, school_id=school_id),
    }
    logger.info("run_full_pipeline: exam=%s, results=%s", exam_id, results)
    return results
