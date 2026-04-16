from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.modules.adaptive.models import QuestionDaOverride, DaKnowledgePointMap


async def resolve_da_ids(
    db: AsyncSession,
    *,
    question_id: str,
    knowledge_point_ids: list[str],
) -> list[tuple[str, float]]:
    """将题目解析为 DA 列表。

    策略 C + override:
    1. 查 question_da_override（人工覆盖，优先）
    2. 否则走 knowledge_point → DA 映射

    Returns: [(da_id, weight), ...]
    """
    # 1. 查 override
    stmt = select(QuestionDaOverride).where(
        QuestionDaOverride.question_id == question_id
    )
    result = await db.execute(stmt)
    override = result.scalar_one_or_none()
    if override is not None:
        return [(da_id, 1.0) for da_id in override.da_ids]

    # 2. 走知识点映射
    if not knowledge_point_ids:
        return []

    stmt = select(DaKnowledgePointMap).where(
        DaKnowledgePointMap.knowledge_point_id.in_(knowledge_point_ids)
    )
    result = await db.execute(stmt)
    rows = result.all()

    # 去重：同一 DA 可能被多个知识点映射到，取最大 weight
    da_map: dict[str, float] = {}
    for row in rows:
        # SQLAlchemy result.all() returns Row tuples when selecting models
        if hasattr(row, 'da_id'):
            da_id, weight = row.da_id, row.weight
        else:
            da_id, weight = row[0].da_id, row[0].weight
        da_map[da_id] = max(da_map.get(da_id, 0.0), weight)

    return [(da_id, w) for da_id, w in da_map.items()]
