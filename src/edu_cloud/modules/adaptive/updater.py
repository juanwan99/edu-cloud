from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.modules.adaptive.models import (
    AnswerLog, StudentDaMastery, DaBktParams,
)
from edu_cloud.modules.adaptive.bkt_engine import bkt_update, BktParams, DEFAULT_PARAMS
from edu_cloud.modules.adaptive.da_mapper import resolve_da_ids

TZ_CN = timezone(timedelta(hours=8))


async def _get_bkt_params(db: AsyncSession, da_id: str) -> BktParams:
    """获取 DA 的 BKT 参数，不存在则用默认值"""
    stmt = select(DaBktParams).where(DaBktParams.da_id == da_id)
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        return DEFAULT_PARAMS
    return BktParams(
        p_init=row.p_init, p_transit=row.p_transit,
        p_guess=row.p_guess, p_slip=row.p_slip,
    )


async def _get_or_create_mastery(
    db: AsyncSession, student_id: str, da_id: str, school_id: str | None,
) -> StudentDaMastery:
    """获取或创建 student_da_mastery 记录"""
    stmt = select(StudentDaMastery).where(
        StudentDaMastery.school_id == school_id,
        StudentDaMastery.student_id == student_id,
        StudentDaMastery.da_id == da_id,
    )
    result = await db.execute(stmt)
    mastery = result.scalar_one_or_none()
    if mastery is not None:
        return mastery

    params = await _get_bkt_params(db, da_id)
    mastery = StudentDaMastery(
        student_id=student_id,
        da_id=da_id,
        mastery_prob=params.p_init,
        attempt_count=0,
        correct_count=0,
        school_id=school_id,
    )
    db.add(mastery)
    await db.flush()
    return mastery


async def process_answer(
    db: AsyncSession,
    *,
    student_id: str,
    question_id: str,
    knowledge_point_ids: list[str],
    correct: bool,
    school_id: str | None = None,
    exam_id: str | None = None,
    source_type: str = "exam",
    score_rate: float | None = None,
    elapsed_ms: int | None = None,
) -> dict:
    """处理一次作答：写 answer_log → 映射 DA → BKT 更新。

    Returns: {da_count: int, updated_das: [{da_id, old_mastery, new_mastery, state}]}
    """
    # 1. 解析 DA
    da_list = await resolve_da_ids(db, question_id=question_id, knowledge_point_ids=knowledge_point_ids)
    da_id_list = [da_id for da_id, _ in da_list]

    # 2. 写 answer_log
    now = datetime.now(TZ_CN)
    log = AnswerLog(
        student_id=student_id,
        question_id=question_id,
        exam_id=exam_id,
        da_ids=da_id_list,
        correct=correct,
        score_rate=score_rate,
        elapsed_ms=elapsed_ms,
        source_type=source_type,
        school_id=school_id,
    )
    db.add(log)

    # 3. 逐 DA 更新 BKT
    updated_das = []
    for da_id, weight in da_list:
        if weight < 0.5:
            continue  # 极低权重 DA 跳过
        mastery = await _get_or_create_mastery(db, student_id, da_id, school_id)
        old_prob = mastery.mastery_prob

        params = await _get_bkt_params(db, da_id)
        new_prob = bkt_update(old_prob, is_correct=correct, params=params)

        mastery.mastery_prob = new_prob
        mastery.attempt_count += 1
        if correct:
            mastery.correct_count += 1
        mastery.last_answer_at = now

        from edu_cloud.modules.adaptive.bkt_engine import classify_da_state
        state = classify_da_state(new_prob, mastery.attempt_count)

        updated_das.append({
            "da_id": da_id,
            "old_mastery": round(old_prob, 4),
            "new_mastery": round(new_prob, 4),
            "state": state,
        })

    await db.commit()

    return {"da_count": len(da_list), "updated_das": updated_das}
