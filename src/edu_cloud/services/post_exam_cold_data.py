"""考后冷数据流水线 owner 应用服务（模块外）。

将考试完成后的冷数据生成逻辑——考试快照 `StudentExamSnapshot`、知识点掌握度
`StudentKnowledgeMastery`、错误模式 `StudentErrorPattern`，以及有效分权威规则
`_get_effective_score` / `_get_effective_scores_for_subject` 与一键编排
`run_full_pipeline`——从 pipeline 模块上移到模块外服务边界，使 pipeline 模块不再
直接 import `exam` / `scan` / `grading` / `knowledge` / `knowledge_tree` / `profile`
/ `student`，一次性拆掉 pipeline 的 7 条直接依赖边（D-03I）。pipeline 仍是考后冷数据
流水线的对外 owner 命名空间，`pipeline.service` 经 re-export 保留旧函数名以维持公共
导入与测试 patch 命名空间兼容。

对外契约保持不变：
- `run_full_pipeline` / `generate_exam_snapshots` / `update_knowledge_mastery` /
  `update_error_patterns` / `_get_effective_score` 经 `pipeline.service` re-export，
  既有调用点（exam `publish_service`、exam_import、编排服务
  `services.post_exam_pipeline` / `services.exam_publish_pipeline`）与测试 patch
  （`pipeline.service.*` 命名空间）行为零变更。
- 有效分权威规则、canonical 学生身份归一、幂等（DF-007）、返回计数与历史完全一致。
- 模块内符号与跨服务 owner（题库/错题本制品 `services.post_exam_bank_artifacts`）
  采用调用期局部 import：既避免 services 层导入期耦合 modules，也让上游对
  `pipeline.service.*` 的测试 patch 在本服务命名空间生效（与
  `services.post_exam_adaptive` / `services.post_exam_bank_artifacts` 同范式）。
"""
import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def _get_effective_score(db: AsyncSession, answer_id: str) -> float | None:
    """获取单个答题的最终有效分。

    优先级：GradingResult.final_score（权威单一值）> StudentAnswer.score（客观题自动判分）
    """
    from edu_cloud.modules.scan.models import StudentAnswer
    from edu_cloud.modules.grading.models import GradingResult

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


async def _get_effective_scores_for_subject(
    db: AsyncSession, *, exam_id: str, subject_id: str, school_id: str,
) -> dict[str, list[tuple[str, float, float]]]:
    """本科目每个学生的有效分明细，pipeline 自有局部查询（不依赖 analytics）。

    有效分 = COALESCE(GradingResult.final_score, StudentAnswer.score)，与本服务
    `_get_effective_score` 同一权威规则；inner join Question 限定本科目题目（等价于
    原 valid_question_ids 过滤），跳过缺考与无有效分的答题。

    分组键是 **canonical student id**：扫描数据可能用 UUID（`students.id`）或外部
    条码键（如经验条码）写入 `student_answers.student_id`，同一学生的选择题与主观题
    可能落在不同 raw key。复用模块外共享 resolver `services.student_identity`
    （与 analytics `get_effective_scores` 同一归一化规则）把 raw key 归一到 canonical
    学生，避免同一学生被拆成多个 StudentExamSnapshot（D-03B 回归收口）。
    """
    from edu_cloud.modules.scan.models import StudentAnswer
    from edu_cloud.modules.grading.models import GradingResult
    from edu_cloud.modules.exam.models import Question
    from edu_cloud.services.student_identity import resolve_student_identities

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
    from edu_cloud.modules.exam.models import Exam, Subject
    from edu_cloud.modules.knowledge.models import QuestionKnowledgePoint
    from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode
    from edu_cloud.modules.profile.models import StudentExamSnapshot
    from edu_cloud.modules.student.models import Student

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
    from edu_cloud.modules.exam.models import Subject, Question
    from edu_cloud.modules.scan.models import StudentAnswer
    from edu_cloud.modules.knowledge.models import QuestionKnowledgePoint
    from edu_cloud.modules.profile.models import StudentKnowledgeMastery

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
    from edu_cloud.modules.exam.models import Subject
    from edu_cloud.modules.profile.models import StudentErrorPattern
    from edu_cloud.services.post_exam_bank_artifacts import (
        list_error_book_students_for_subject,
        list_error_book_entries_for_student,
    )

    subjects = await db.execute(
        select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
    )

    updated = 0
    for subj in subjects.scalars().all():
        # 错题本读模型经模块外服务边界获取，pipeline 不再直接 import bank（D-03H）；
        # 错误模式聚合与 profile.StudentErrorPattern 落库仍归本冷数据 owner。
        affected_students = await list_error_book_students_for_subject(
            db, exam_id=exam_id, school_id=school_id, subject_id=subj.id,
        )
        if not affected_students:
            continue

        for stu_id in affected_students:
            error_entries = await list_error_book_entries_for_student(
                db, student_id=stu_id, school_id=school_id, subject_code=subj.code,
            )
            total_errors = len(error_entries)

            type_counts: dict[str, int] = {}
            exam_ids_set: set[str] = set()
            for error_type, eb_exam_id in error_entries:
                etype = error_type or "未分类"
                type_counts[etype] = type_counts.get(etype, 0) + 1
                exam_ids_set.add(eb_exam_id)
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

    跨模块的考后副作用已移出本 owner，由模块外编排服务
    `services.post_exam_pipeline.run_post_exam_pipeline` 串联补齐：
    - analytics 考后预聚合 `exam_analysis`（D-03B）
    - adaptive BKT 掌握度更新 `adaptive_mastery`（D-03E，经
      `services.post_exam_adaptive.update_adaptive_mastery`，pipeline 不再 import adaptive）

    因此 `run_full_pipeline` 只产 pipeline 自有冷数据各步骤，不含 `exam_analysis` /
    `adaptive_mastery`。题库/错题本制品（`populate_bank_questions` /
    `populate_error_books`）经模块外服务 `services.post_exam_bank_artifacts`
    生成（D-03H）。
    """
    from edu_cloud.services.post_exam_bank_artifacts import (
        populate_bank_questions,
        populate_error_books,
    )

    results = {
        "bank_questions": await populate_bank_questions(db, exam_id=exam_id, school_id=school_id),
        "error_books": await populate_error_books(db, exam_id=exam_id, school_id=school_id),
        "exam_snapshots": await generate_exam_snapshots(db, exam_id=exam_id, school_id=school_id),
        "knowledge_mastery": await update_knowledge_mastery(db, exam_id=exam_id, school_id=school_id),
        "error_patterns": await update_error_patterns(db, exam_id=exam_id, school_id=school_id),
    }
    logger.info("run_full_pipeline: exam=%s, results=%s", exam_id, results)
    return results
