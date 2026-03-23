import pytest
from edu_cloud.data.seed_knowledge_math import seed_math_knowledge, MATH_KNOWLEDGE_TREE
from edu_cloud.modules.knowledge.models import KnowledgePoint, GLOBAL_SCHOOL_ID
from sqlalchemy import select, func


@pytest.mark.asyncio
async def test_seed_math_knowledge(db):
    created = await seed_math_knowledge(db)
    assert created == len(MATH_KNOWLEDGE_TREE)

    # 验证总数
    result = await db.execute(select(func.count()).select_from(KnowledgePoint))
    assert result.scalar() == len(MATH_KNOWLEDGE_TREE)

    # 验证树结构：函数(L1) → 导数(L2) → 导数的概念(L3)
    r = await db.execute(select(KnowledgePoint).where(KnowledgePoint.code == "MATH_FUNC_DERIV_CONCEPT"))
    kp = r.scalar_one()
    assert kp.level == 3
    assert kp.parent_id is not None

    # 验证幂等：再跑一次不报错、不重复
    created2 = await seed_math_knowledge(db)
    assert created2 == 0
    result2 = await db.execute(select(func.count()).select_from(KnowledgePoint))
    assert result2.scalar() == len(MATH_KNOWLEDGE_TREE)


@pytest.mark.asyncio
async def test_seed_with_preexisting_school_nodes(db):
    """TG-002: 学校级同码节点存在时，seed 仍正确创建全局节点。"""
    # 预置学校级节点（school_id 非 NULL）
    db.add(KnowledgePoint(
        code="MATH_FUNC", name="函数(学校版)", course_code="SX",
        level=1, school_id="school-001",
    ))
    await db.commit()

    # seed 全局节点
    created = await seed_math_knowledge(db)
    assert created == len(MATH_KNOWLEDGE_TREE)  # 全部全局节点都是新建

    # 验证全局 + 学校节点共存
    result = await db.execute(select(func.count()).select_from(KnowledgePoint))
    total = result.scalar()
    assert total == len(MATH_KNOWLEDGE_TREE) + 1  # 48 全局 + 1 学校


@pytest.mark.asyncio
async def test_seed_with_partial_global_nodes(db):
    """TG-002: 部分全局节点已存在时，seed 只补齐缺失的。"""
    # 预置 3 个全局节点
    db.add(KnowledgePoint(code="MATH_FUNC", name="函数", course_code="SX", level=1, school_id=GLOBAL_SCHOOL_ID))
    db.add(KnowledgePoint(code="MATH_TRIG", name="三角函数", course_code="SX", level=1, school_id=GLOBAL_SCHOOL_ID))
    db.add(KnowledgePoint(code="MATH_SEQ", name="数列", course_code="SX", level=1, school_id=GLOBAL_SCHOOL_ID))
    await db.commit()

    created = await seed_math_knowledge(db)
    assert created == len(MATH_KNOWLEDGE_TREE) - 3  # 跳过 3 个已有的

    # 验证总数
    result = await db.execute(
        select(func.count()).select_from(KnowledgePoint)
        .where(KnowledgePoint.school_id == GLOBAL_SCHOOL_ID)
    )
    assert result.scalar() == len(MATH_KNOWLEDGE_TREE)
