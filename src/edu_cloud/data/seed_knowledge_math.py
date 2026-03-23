"""数学知识点标准树 — 按高中课标预置，约 48 个节点（精简版）。"""

MATH_KNOWLEDGE_TREE = [
    # (code, name, level, parent_code_or_None, grade_hint)
    ("MATH_FUNC", "函数", 1, None, None),
    ("MATH_FUNC_CONCEPT", "函数概念与性质", 2, "MATH_FUNC", "高一上"),
    ("MATH_FUNC_CONCEPT_DOMAIN", "函数的定义域", 3, "MATH_FUNC_CONCEPT", "高一上"),
    ("MATH_FUNC_CONCEPT_RANGE", "函数的值域", 3, "MATH_FUNC_CONCEPT", "高一上"),
    ("MATH_FUNC_CONCEPT_MONO", "函数的单调性", 3, "MATH_FUNC_CONCEPT", "高一上"),
    ("MATH_FUNC_CONCEPT_PARITY", "函数的奇偶性", 3, "MATH_FUNC_CONCEPT", "高一上"),
    ("MATH_FUNC_ELEM", "基本初等函数", 2, "MATH_FUNC", "高一上"),
    ("MATH_FUNC_ELEM_EXP", "指数函数", 3, "MATH_FUNC_ELEM", "高一上"),
    ("MATH_FUNC_ELEM_LOG", "对数函数", 3, "MATH_FUNC_ELEM", "高一上"),
    ("MATH_FUNC_ELEM_POWER", "幂函数", 3, "MATH_FUNC_ELEM", "高一上"),
    ("MATH_FUNC_DERIV", "导数", 2, "MATH_FUNC", "高二下"),
    ("MATH_FUNC_DERIV_CONCEPT", "导数的概念", 3, "MATH_FUNC_DERIV", "高二下"),
    ("MATH_FUNC_DERIV_GEO", "导数的几何意义", 3, "MATH_FUNC_DERIV", "高二下"),
    ("MATH_FUNC_DERIV_APP", "导数的应用", 3, "MATH_FUNC_DERIV", "高二下"),

    ("MATH_TRIG", "三角函数", 1, None, None),
    ("MATH_TRIG_DEF", "三角函数定义", 2, "MATH_TRIG", "高一下"),
    ("MATH_TRIG_IDENTITY", "三角恒等变换", 2, "MATH_TRIG", "高一下"),
    ("MATH_TRIG_SINE_RULE", "正弦定理", 2, "MATH_TRIG", "高一下"),
    ("MATH_TRIG_COSINE_RULE", "余弦定理", 2, "MATH_TRIG", "高一下"),
    ("MATH_TRIG_GRAPH", "三角函数图像与性质", 2, "MATH_TRIG", "高一下"),

    ("MATH_SEQ", "数列", 1, None, None),
    ("MATH_SEQ_ARITH", "等差数列", 2, "MATH_SEQ", "高一下"),
    ("MATH_SEQ_GEOM", "等比数列", 2, "MATH_SEQ", "高一下"),
    ("MATH_SEQ_SUM", "数列求和", 2, "MATH_SEQ", "高二上"),

    ("MATH_GEOM_SOLID", "立体几何", 1, None, None),
    ("MATH_GEOM_SOLID_BASIC", "空间几何体", 2, "MATH_GEOM_SOLID", "高二上"),
    ("MATH_GEOM_SOLID_PARALLEL", "平行关系", 2, "MATH_GEOM_SOLID", "高二上"),
    ("MATH_GEOM_SOLID_PERP", "垂直关系", 2, "MATH_GEOM_SOLID", "高二上"),
    ("MATH_GEOM_SOLID_VECTOR", "空间向量", 2, "MATH_GEOM_SOLID", "高二下"),

    ("MATH_GEOM_ANALYTIC", "解析几何", 1, None, None),
    ("MATH_GEOM_ANALYTIC_LINE", "直线方程", 2, "MATH_GEOM_ANALYTIC", "高二上"),
    ("MATH_GEOM_ANALYTIC_CIRCLE", "圆的方程", 2, "MATH_GEOM_ANALYTIC", "高二上"),
    ("MATH_GEOM_ANALYTIC_ELLIPSE", "椭圆", 2, "MATH_GEOM_ANALYTIC", "高二下"),
    ("MATH_GEOM_ANALYTIC_HYPERBOLA", "双曲线", 2, "MATH_GEOM_ANALYTIC", "高二下"),
    ("MATH_GEOM_ANALYTIC_PARABOLA", "抛物线", 2, "MATH_GEOM_ANALYTIC", "高二下"),

    ("MATH_PROB", "概率与统计", 1, None, None),
    ("MATH_PROB_COUNT", "排列组合", 2, "MATH_PROB", "高二上"),
    ("MATH_PROB_BINOMIAL", "二项式定理", 2, "MATH_PROB", "高二上"),
    ("MATH_PROB_BASIC", "古典概型", 2, "MATH_PROB", "高一下"),
    ("MATH_PROB_COND", "条件概率", 2, "MATH_PROB", "高二下"),
    ("MATH_PROB_DIST", "离散随机变量", 2, "MATH_PROB", "高二下"),
    ("MATH_PROB_STAT", "统计推断", 2, "MATH_PROB", "高二下"),

    ("MATH_LOGIC", "集合与逻辑", 1, None, None),
    ("MATH_LOGIC_SET", "集合", 2, "MATH_LOGIC", "高一上"),
    ("MATH_LOGIC_PROP", "命题与逻辑", 2, "MATH_LOGIC", "高一上"),
    ("MATH_LOGIC_INEQUALITY", "不等式", 2, "MATH_LOGIC", "高一上"),

    ("MATH_VECTOR", "平面向量", 1, None, None),
    ("MATH_VECTOR_CONCEPT", "向量的概念与运算", 2, "MATH_VECTOR", "高一下"),
    ("MATH_VECTOR_COORD", "向量的坐标运算", 2, "MATH_VECTOR", "高一下"),
    ("MATH_VECTOR_DOT", "向量的数量积", 2, "MATH_VECTOR", "高一下"),
]


async def seed_math_knowledge(db) -> int:
    """Seed 数学知识点树。返回创建的节点数。幂等：已存在则跳过。"""
    from sqlalchemy import select
    from edu_cloud.modules.knowledge.models import KnowledgePoint, GLOBAL_SCHOOL_ID

    # R2-003: 查全局预置节点（school_id == GLOBAL_SCHOOL_ID）
    existing = await db.execute(
        select(KnowledgePoint.code).where(
            KnowledgePoint.course_code == "SX",
            KnowledgePoint.school_id == GLOBAL_SCHOOL_ID,
        )
    )
    existing_codes = set(row[0] for row in existing.all())

    code_to_id = {}
    created = 0
    for code, name, level, parent_code, grade_hint in MATH_KNOWLEDGE_TREE:
        if code in existing_codes:
            r = await db.execute(
                select(KnowledgePoint.id).where(
                    KnowledgePoint.code == code,
                    KnowledgePoint.school_id == GLOBAL_SCHOOL_ID,
                )
            )
            code_to_id[code] = r.scalar_one()
            continue

        kp = KnowledgePoint(
            code=code, name=name, course_code="SX", level=level,
            grade_hint=grade_hint, school_id=GLOBAL_SCHOOL_ID,
        )
        db.add(kp)
        await db.flush()
        code_to_id[code] = kp.id
        created += 1

    # 第二遍：设 parent_id
    for code, name, level, parent_code, grade_hint in MATH_KNOWLEDGE_TREE:
        if parent_code and parent_code in code_to_id:
            kp_id = code_to_id[code]
            parent_id = code_to_id[parent_code]
            await db.execute(
                KnowledgePoint.__table__.update()
                .where(KnowledgePoint.__table__.c.id == kp_id)
                .values(parent_id=parent_id)
            )

    await db.commit()
    return created
