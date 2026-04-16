"""知识点业务逻辑（从 exam-ai 迁入）。"""
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.knowledge.models import KnowledgePoint, QuestionKnowledgePoint
from edu_cloud.services.exceptions import NotFoundError, ConflictError

logger = logging.getLogger(__name__)

GLOBAL_SCHOOL_ID = "__GLOBAL__"


async def list_knowledge_points(
    db: AsyncSession, *, course_code: str, parent_id: str | None = None,
    school_id: str | None = None,
) -> list[KnowledgePoint]:
    stmt = select(KnowledgePoint).where(KnowledgePoint.course_code == course_code)
    if parent_id is not None:
        stmt = stmt.where(KnowledgePoint.parent_id == parent_id)
    else:
        stmt = stmt.where(KnowledgePoint.parent_id.is_(None))
    if school_id is not None:
        stmt = stmt.where(
            (KnowledgePoint.school_id == GLOBAL_SCHOOL_ID) | (KnowledgePoint.school_id == school_id)
        )
    result = await db.execute(stmt.order_by(KnowledgePoint.code))
    return list(result.scalars().all())


async def get_knowledge_point(
    db: AsyncSession, *, kp_id: str, school_id: str | None = None,
) -> KnowledgePoint:
    stmt = select(KnowledgePoint).where(KnowledgePoint.id == kp_id)
    if school_id is not None:
        stmt = stmt.where(
            (KnowledgePoint.school_id == GLOBAL_SCHOOL_ID) | (KnowledgePoint.school_id == school_id)
        )
    kp = (await db.execute(stmt)).scalar_one_or_none()
    if not kp:
        raise NotFoundError("Knowledge point not found")
    return kp


async def get_children(
    db: AsyncSession, *, parent_id: str, school_id: str | None = None,
) -> list[KnowledgePoint]:
    stmt = select(KnowledgePoint).where(KnowledgePoint.parent_id == parent_id)
    if school_id is not None:
        stmt = stmt.where(
            (KnowledgePoint.school_id == GLOBAL_SCHOOL_ID) | (KnowledgePoint.school_id == school_id)
        )
    result = await db.execute(stmt.order_by(KnowledgePoint.code))
    return list(result.scalars().all())


async def create_knowledge_point(
    db: AsyncSession, *,
    code: str, name: str, course_code: str, level: int = 1,
    parent_id: str | None = None, school_id: str | None = None,
    description: str | None = None, grade_hint: str | None = None,
) -> KnowledgePoint:
    kp = KnowledgePoint(
        code=code, name=name, course_code=course_code, level=level,
        parent_id=parent_id, school_id=school_id or GLOBAL_SCHOOL_ID,
        description=description, grade_hint=grade_hint,
    )
    db.add(kp)
    await db.commit()
    await db.refresh(kp)
    logger.info("create_kp: id=%s, code=%s, name=%s", kp.id, code, name)
    return kp


async def link_question(
    db: AsyncSession, *, question_id: str, knowledge_point_id: str, is_primary: bool = True,
) -> QuestionKnowledgePoint:
    from sqlalchemy.exc import IntegrityError
    link = QuestionKnowledgePoint(
        question_id=question_id,
        knowledge_point_id=knowledge_point_id,
        is_primary=is_primary,
    )
    db.add(link)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictError("Question already linked to this knowledge point")
    await db.refresh(link)
    return link


async def get_question_knowledge_points(
    db: AsyncSession, *, question_id: str,
) -> list[KnowledgePoint]:
    result = await db.execute(
        select(KnowledgePoint)
        .join(QuestionKnowledgePoint, QuestionKnowledgePoint.knowledge_point_id == KnowledgePoint.id)
        .where(QuestionKnowledgePoint.question_id == question_id)
    )
    return list(result.scalars().all())
