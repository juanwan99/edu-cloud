"""题库 + 错题本业务逻辑（从 exam-ai 迁入）。"""
import logging
from collections import defaultdict
from sqlalchemy import select, func, String
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.bank.models import BankQuestion, StudentErrorBook
from edu_cloud.services.exceptions import NotFoundError

logger = logging.getLogger(__name__)


async def get_bank_question(
    db: AsyncSession, *, bank_question_id: str, school_id: str,
) -> BankQuestion:
    result = await db.execute(
        select(BankQuestion).where(BankQuestion.id == bank_question_id, BankQuestion.school_id == school_id)
    )
    bq = result.scalar_one_or_none()
    if not bq:
        raise NotFoundError("Bank question not found")
    return bq


async def list_bank_questions(
    db: AsyncSession, *, school_id: str, question_type: str | None = None,
    min_difficulty: float | None = None, max_difficulty: float | None = None,
    limit: int = 50,
) -> list[BankQuestion]:
    stmt = select(BankQuestion).where(BankQuestion.school_id == school_id)
    if question_type:
        stmt = stmt.where(BankQuestion.question_type == question_type)
    if min_difficulty is not None:
        stmt = stmt.where(BankQuestion.difficulty >= min_difficulty)
    if max_difficulty is not None:
        stmt = stmt.where(BankQuestion.difficulty <= max_difficulty)
    stmt = stmt.order_by(BankQuestion.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_student_error_book(
    db: AsyncSession, *, student_id: str, school_id: str,
    mastery_status: str | None = None, limit: int = 50,
) -> list[StudentErrorBook]:
    stmt = (
        select(StudentErrorBook)
        .where(StudentErrorBook.student_id == student_id, StudentErrorBook.school_id == school_id)
    )
    if mastery_status:
        stmt = stmt.where(StudentErrorBook.mastery_status == mastery_status)
    stmt = stmt.order_by(StudentErrorBook.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def search_questions(
    db: AsyncSession, *, school_id: str,
    question_type: str | None = None,
    difficulty_level: str | None = None,
    source: str | None = None,
    tags: list[str] | None = None,
    knowledge_point_ids: list[str] | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """多条件 AND 组合搜索题库，返回分页结果。"""
    base = select(BankQuestion).where(BankQuestion.school_id == school_id)

    if question_type:
        base = base.where(BankQuestion.question_type == question_type)
    if difficulty_level:
        base = base.where(BankQuestion.difficulty_level == difficulty_level)
    if source:
        base = base.where(BankQuestion.source == source)
    if keyword:
        base = base.where(BankQuestion.content_text.contains(keyword))

    # JSON 列筛选：SQLite 用 LIKE 兼容，PG 用原生 JSON 运算
    if tags:
        for tag in tags:
            base = base.where(BankQuestion.tags.cast(String).contains(tag))
    if knowledge_point_ids:
        for kp_id in knowledge_point_ids:
            base = base.where(
                BankQuestion.knowledge_point_ids.cast(String).contains(kp_id)
            )

    # 总数
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # 分页
    offset = (page - 1) * page_size
    items_stmt = base.order_by(BankQuestion.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(items_stmt)
    items = list(result.scalars().all())

    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_questions_stats_overview(
    db: AsyncSession, *, school_id: str,
) -> dict:
    """题库统计概览：总数 + 按 question_type / difficulty_level / source 分组。"""
    base_where = BankQuestion.school_id == school_id

    # 总数
    total = (await db.execute(
        select(func.count()).where(base_where)
    )).scalar() or 0

    # 按 question_type 分组
    by_type_rows = (await db.execute(
        select(BankQuestion.question_type, func.count().label("cnt"))
        .where(base_where)
        .group_by(BankQuestion.question_type)
    )).all()
    by_question_type = {row[0]: row[1] for row in by_type_rows if row[0]}

    # 按 difficulty_level 分组
    by_diff_rows = (await db.execute(
        select(BankQuestion.difficulty_level, func.count().label("cnt"))
        .where(base_where)
        .group_by(BankQuestion.difficulty_level)
    )).all()
    by_difficulty_level = {row[0]: row[1] for row in by_diff_rows if row[0]}

    # 按 source 分组
    by_src_rows = (await db.execute(
        select(BankQuestion.source, func.count().label("cnt"))
        .where(base_where)
        .group_by(BankQuestion.source)
    )).all()
    by_source = {row[0]: row[1] for row in by_src_rows if row[0]}

    return {
        "total_count": total,
        "by_question_type": by_question_type,
        "by_difficulty_level": by_difficulty_level,
        "by_source": by_source,
    }


async def get_error_knowledge_summary(
    db: AsyncSession, *, student_id: str, school_id: str,
) -> list[dict]:
    """按知识点聚合学生错题：统计每个知识点的错题数量、最新错题时间、掌握状态。

    从 StudentErrorBook 读取每条错题的 knowledge_point_ids（JSON 数组），
    展开后按知识点 ID 聚合。返回按 error_count DESC 排序的 TOP 20。
    """
    # 查询该学生所有错题
    result = await db.execute(
        select(
            StudentErrorBook.knowledge_point_ids,
            StudentErrorBook.mastery_status,
            StudentErrorBook.created_at,
        )
        .where(
            StudentErrorBook.student_id == student_id,
            StudentErrorBook.school_id == school_id,
        )
    )
    rows = result.all()
    if not rows:
        return []

    # 展开 knowledge_point_ids 并聚合
    kp_stats: dict[str, dict] = defaultdict(lambda: {
        "error_count": 0,
        "latest_error_date": None,
        "statuses": [],
    })
    for kp_ids, mastery_status, created_at in rows:
        if not kp_ids:
            continue
        for kp_id in kp_ids:
            entry = kp_stats[kp_id]
            entry["error_count"] += 1
            entry["statuses"].append(mastery_status)
            if entry["latest_error_date"] is None or (created_at and created_at > entry["latest_error_date"]):
                entry["latest_error_date"] = created_at

    # 确定每个知识点的综合掌握状态：有 unmastered 则 unmastered，有 practicing 则 practicing，否则 mastered
    summary = []
    for kp_id, data in kp_stats.items():
        statuses = data["statuses"]
        if "unmastered" in statuses:
            mastery = "unmastered"
        elif "practicing" in statuses:
            mastery = "practicing"
        else:
            mastery = "mastered"
        summary.append({
            "knowledge_point_id": kp_id,
            "error_count": data["error_count"],
            "latest_error_date": data["latest_error_date"].isoformat() if data["latest_error_date"] else None,
            "mastery_status": mastery,
        })

    # 按 error_count DESC 排序，取 TOP 20
    summary.sort(key=lambda x: x["error_count"], reverse=True)
    return summary[:20]


async def get_recommended_practice(
    db: AsyncSession, *, student_id: str, school_id: str, limit: int = 10,
) -> list[dict]:
    """基于薄弱知识点推荐练习题。

    1. 调用 get_error_knowledge_summary 获取薄弱知识点
    2. 从 BankQuestion 中筛选同 knowledge_point_ids 的题目
    3. 排除已在错题本中的题（已做错的）
    4. 按 difficulty ASC 排序（先易后难）
    """
    kp_summary = await get_error_knowledge_summary(db, student_id=student_id, school_id=school_id)
    if not kp_summary:
        return []

    weak_kp_ids = [item["knowledge_point_id"] for item in kp_summary]

    # 获取学生已做错的 bank_question_id 集合（排除用）
    err_result = await db.execute(
        select(StudentErrorBook.bank_question_id)
        .where(
            StudentErrorBook.student_id == student_id,
            StudentErrorBook.school_id == school_id,
            StudentErrorBook.bank_question_id.isnot(None),
        )
    )
    errored_bq_ids = {row[0] for row in err_result.all()}

    # 从题库中找同知识点的题目（SQLite JSON 用 LIKE 匹配）
    stmt = select(BankQuestion).where(BankQuestion.school_id == school_id)
    # 筛选知识点：任一薄弱知识点匹配即可
    from sqlalchemy import or_
    kp_filters = [BankQuestion.knowledge_point_ids.cast(String).contains(kp_id) for kp_id in weak_kp_ids]
    if kp_filters:
        stmt = stmt.where(or_(*kp_filters))

    result = await db.execute(stmt)
    candidates = list(result.scalars().all())

    # 排除已做错的
    recommendations = [q for q in candidates if q.id not in errored_bq_ids]

    # 按 difficulty ASC 排序（None 排最后）
    recommendations.sort(key=lambda q: q.difficulty if q.difficulty is not None else 999)

    # 构造返回数据
    return [
        {
            "id": q.id,
            "content_text": q.content_text,
            "question_type": q.question_type,
            "max_score": q.max_score,
            "difficulty": q.difficulty,
            "difficulty_level": q.difficulty_level,
            "knowledge_point_ids": q.knowledge_point_ids,
        }
        for q in recommendations[:limit]
    ]


async def get_error_book_stats(
    db: AsyncSession, *, student_id: str, school_id: str,
) -> dict:
    result = await db.execute(
        select(
            StudentErrorBook.mastery_status,
            func.count().label("count"),
        )
        .where(StudentErrorBook.student_id == student_id, StudentErrorBook.school_id == school_id)
        .group_by(StudentErrorBook.mastery_status)
    )
    stats = {row[0]: row[1] for row in result.all()}
    return {
        "total": sum(stats.values()),
        "unmastered": stats.get("unmastered", 0),
        "practicing": stats.get("practicing", 0),
        "mastered": stats.get("mastered", 0),
    }
