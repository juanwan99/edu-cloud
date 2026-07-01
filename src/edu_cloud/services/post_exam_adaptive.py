"""考后自适应掌握度更新应用服务（模块外）。

将考试作答写入 adaptive 模块（`answer_logs` + BKT 更新）的副作用从 pipeline 模块
上移到模块外服务边界，使 pipeline 不再直接 import `edu_cloud.modules.adaptive`，
拆掉 `pipeline -> adaptive` 依赖边（D-03E）。冷数据 owner 已上移模块外
`services.post_exam_cold_data`（D-03I），本服务只负责把考后作答桥接到 adaptive 的
BKT 更新。

对外契约保持不变：遍历非缺考作答，对每道有 max_score 的题幂等调用
`adaptive.process_answer`（按 `AnswerLog` 存在性跳过重复），返回处理的答题数；
有效分沿用冷数据 owner 权威规则 `services.post_exam_cold_data._get_effective_score`
（调用期局部 import，避免 services → modules 的导入期耦合）。失败的非阻塞降级由调用方
（`pipeline.on_exam_published` event handler）负责，编排路径与历史一致按硬调用聚合。
"""
import logging
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def update_adaptive_mastery(db: AsyncSession, *, exam_id: str, school_id: str) -> int:
    """将考试作答数据写入 adaptive 模块（answer_logs + BKT 更新）。

    遍历 StudentAnswer 记录，对每道题调用 process_answer。返回处理的答题数。

    模块内符号采用调用期局部 import：既避免 services 层导入期耦合 modules，
    也让上游测试 patch 在本服务命名空间生效。
    """
    from edu_cloud.modules.adaptive.updater import process_answer
    from edu_cloud.modules.adaptive.models import AnswerLog
    from edu_cloud.modules.exam.models import Subject, Question
    from edu_cloud.modules.scan.models import StudentAnswer
    from edu_cloud.modules.knowledge.models import QuestionKnowledgePoint
    from edu_cloud.services.post_exam_cold_data import _get_effective_score
    from edu_cloud.services.student_identity import resolve_student_identities

    # 查询本考试所有题目（含 max_score）
    subjects = await db.execute(
        select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
    )
    subject_rows = subjects.scalars().all()
    question_map: dict[str, float] = {}  # q_id → max_score
    for subj in subject_rows:
        qs = await db.execute(
            select(Question.id, Question.max_score).where(Question.subject_id == subj.id)
        )
        for q_id, max_score in qs.all():
            if max_score and max_score > 0:
                question_map[q_id] = max_score

    if not question_map:
        return 0

    # 通过 QuestionKnowledgePoint 关联表获取知识点（与已有 pipeline 一致）
    kp_map: dict[str, list[str]] = defaultdict(list)
    for q_id in question_map:
        kps = await db.execute(
            select(QuestionKnowledgePoint.concept_id).where(
                QuestionKnowledgePoint.question_id == q_id
            )
        )
        kp_map[q_id] = [row[0] for row in kps.all()]

    count = 0
    for q_id, max_score in question_map.items():
        kp_ids = kp_map.get(q_id, [])

        # 查询该题的非缺考学生作答
        answers = await db.execute(
            select(StudentAnswer).where(
                StudentAnswer.question_id == q_id,
                StudentAnswer.school_id == school_id,
                StudentAnswer.is_absent == False,  # noqa: E712 — N001: 过滤缺考
            )
        )
        answer_rows = answers.scalars().all()
        identities = await resolve_student_identities(
            db,
            school_id=school_id,
            raw_student_ids=[answer.student_id for answer in answer_rows],
        )

        for answer in answer_rows:
            raw_student_id = str(answer.student_id)
            identity = identities.get(raw_student_id)
            student_id = (
                identity.canonical_student_id
                if identity and identity.canonical_student_id
                else raw_student_id
            )

            # 幂等检查
            existing = await db.execute(
                select(AnswerLog).where(
                    AnswerLog.school_id == school_id,
                    AnswerLog.exam_id == exam_id,
                    AnswerLog.student_id == student_id,
                    AnswerLog.question_id == q_id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue

            effective_score = await _get_effective_score(db, answer.id)
            is_correct = (effective_score or 0) >= max_score * 0.6

            await process_answer(
                db,
                student_id=student_id,
                question_id=q_id,
                knowledge_point_ids=kp_ids,
                correct=is_correct,
                school_id=school_id,
                exam_id=exam_id,
                score_rate=effective_score / max_score if effective_score is not None else None,
                source_type="exam",
            )
            count += 1

    logger.info("update_adaptive_mastery: exam=%s, processed=%d", exam_id, count)
    return count
