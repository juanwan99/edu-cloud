import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.modules.adaptive.models import StudentDaMastery, DaCatalogSnapshot
from edu_cloud.modules.adaptive.bkt_engine import classify_da_state
from edu_cloud.modules.adaptive.path_planner import plan_learning_path
from edu_cloud.modules.adaptive.question_selector import select_transfer_band, filter_candidates

logger = logging.getLogger(__name__)


async def get_da_study_unit_map(db: AsyncSession) -> dict[str, str]:
    """从快照获取 DA→SU 映射（取第一个 SU）"""
    stmt = select(DaCatalogSnapshot)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    mapping = {}
    for row in rows:
        su_ids = row.study_unit_ids or []
        if su_ids:
            mapping[row.da_id] = su_ids[0]
    return mapping


async def get_su_prerequisites(db: AsyncSession) -> dict[str, list[str]]:
    """从快照推导 SU 前置关系（简化版，V1 从 knowledge.db 精确获取）"""
    return {}


async def get_candidate_questions(db: AsyncSession, da_ids: list[str]) -> list[dict]:
    """获取候选题目（V1 从 MCP 精确获取，MVP 返回占位）"""
    return []


async def diagnose_and_recommend(
    db: AsyncSession,
    *,
    student_id: str,
    school_id: str,
    da_ids: list[str] | None = None,
) -> dict:
    """诊断学生掌握度并推荐学习路径。

    Returns: {da_states, learning_path, recommended_questions}
    """
    logger.info("diagnose_and_recommend: student_id=%s, school_id=%s, da_ids=%s",
                student_id, school_id, da_ids)
    # 1. 查询学生所有 DA 掌握度
    stmt = select(StudentDaMastery).where(
        StudentDaMastery.school_id == school_id,
        StudentDaMastery.student_id == student_id,
    )
    if da_ids:
        stmt = stmt.where(StudentDaMastery.da_id.in_(da_ids))
    result = await db.execute(stmt)
    mastery_rows = result.scalars().all()

    # 2. 构建 mastery_map
    mastery_map = {}
    da_states = []
    for row in mastery_rows:
        state = classify_da_state(row.mastery_prob, row.attempt_count)
        mastery_map[row.da_id] = {
            "mastery": row.mastery_prob,
            "state": state,
        }
        da_states.append({
            "da_id": row.da_id,
            "mastery": round(row.mastery_prob, 4),
            "state": state,
            "attempt_count": row.attempt_count,
        })

    # 3. 路径规划
    da_to_su = await get_da_study_unit_map(db)
    su_prereqs = await get_su_prerequisites(db)
    learning_path = plan_learning_path(mastery_map, da_to_su, su_prereqs)

    # 4. 选题（MVP 简化版）
    recommended_questions = []
    for item in learning_path[:3]:
        band = select_transfer_band(item["state"])
        candidates = await get_candidate_questions(db, item["da_ids"])
        selected = filter_candidates(candidates, target_band=band, limit=3)
        recommended_questions.extend(selected)

    return {
        "da_states": da_states,
        "learning_path": learning_path,
        "recommended_questions": recommended_questions,
    }
