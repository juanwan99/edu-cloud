"""答题卡模块共享工具函数。"""
from __future__ import annotations

import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.card.models import CardSkeleton
from edu_cloud.services.card_workflow import Subject


def _q_sort_key(q):
    m = re.match(r'(\d+)', q.name)
    return (0, int(m.group(1))) if m else (1, q.name)


async def get_skeleton_data(
    subject_code: str, school_id: str | None, db: AsyncSession
) -> dict:
    """获取骨架数据：优先数据库，回退内置模板。"""
    skel_stmt = select(CardSkeleton).where(CardSkeleton.subject_code == subject_code)
    if school_id:
        skel_stmt = skel_stmt.where(CardSkeleton.school_id == school_id)
    result = await db.execute(skel_stmt)
    skeleton_row = result.scalars().first()
    if skeleton_row:
        return skeleton_row.skeleton_data

    from edu_cloud.services.card_workflow import Question
    from edu_cloud.modules.card.rendering.layout import build_skeleton_from_spec

    subj_stmt = select(Subject).where(Subject.code == subject_code)
    if school_id:
        subj_stmt = subj_stmt.where(Subject.school_id == school_id)
    subj_result = await db.execute(subj_stmt)
    subj_row = subj_result.scalars().first()
    if not subj_row:
        raise HTTPException(404, f"科目 {subject_code} 无骨架且无题目数据")

    q_stmt = select(Question).where(Question.subject_id == str(subj_row.id))
    if school_id:
        q_stmt = q_stmt.where(Question.school_id == school_id)
    q_result = await db.execute(q_stmt)
    db_questions = q_result.scalars().all()
    q_list = []
    for i, q in enumerate(sorted(db_questions, key=_q_sort_key)):
        q_list.append({
            "number": i + 1,
            "question_type": q.question_type,
            "options_count": 4,
        })
    return build_skeleton_from_spec(q_list, paper_size="A3", columns=3, exam_number_digits=8)
