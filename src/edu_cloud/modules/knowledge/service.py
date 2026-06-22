"""知识点查询服务（统一到 ConceptGraphNode）。"""
import logging
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.services.knowledge_workflow import ConceptGraphEdge, ConceptGraphNode
from edu_cloud.modules.knowledge.models import QuestionKnowledgePoint
from edu_cloud.services.exceptions import ConflictError

logger = logging.getLogger(__name__)


async def list_knowledge_points(
    db: AsyncSession, *, course_code: str | None = None,
    parent_id: str | None = None, level: str | None = None,
) -> list[ConceptGraphNode]:
    stmt = select(ConceptGraphNode)
    if course_code:
        stmt = stmt.where(ConceptGraphNode.course_code == course_code)
    if level:
        stmt = stmt.where(ConceptGraphNode.node_type == level)
    if parent_id:
        child_ids_stmt = (
            select(ConceptGraphEdge.target_id)
            .where(ConceptGraphEdge.source_id == parent_id,
                   ConceptGraphEdge.relation_type == "contains")
        )
        stmt = stmt.where(ConceptGraphNode.id.in_(child_ids_stmt))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_knowledge_point(db: AsyncSession, *, kp_id: str) -> ConceptGraphNode | None:
    result = await db.execute(
        select(ConceptGraphNode).where(ConceptGraphNode.id == kp_id)
    )
    return result.scalar_one_or_none()


async def get_children(db: AsyncSession, *, parent_id: str) -> list[ConceptGraphNode]:
    child_ids = select(ConceptGraphEdge.target_id).where(
        ConceptGraphEdge.source_id == parent_id,
        ConceptGraphEdge.relation_type == "contains",
    )
    result = await db.execute(
        select(ConceptGraphNode).where(ConceptGraphNode.id.in_(child_ids))
    )
    return list(result.scalars().all())


async def link_question(
    db: AsyncSession, *, question_id: str, concept_id: str,
    is_primary: bool = True, school_id: str | None = None,
) -> QuestionKnowledgePoint:
    if school_id:
        from edu_cloud.services.knowledge_workflow import Question
        from fastapi import HTTPException
        q = (await db.execute(
            select(Question).where(
                Question.id == question_id,
                Question.school_id == school_id,
            )
        )).scalar_one_or_none()
        if not q:
            raise HTTPException(404, "Question not found")
    qkp = QuestionKnowledgePoint(
        question_id=question_id, concept_id=concept_id, is_primary=is_primary,
    )
    db.add(qkp)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(
            f"Link already exists: question={question_id}, concept={concept_id}"
        ) from exc
    return qkp


async def get_question_knowledge_points(
    db: AsyncSession, *, question_id: str, school_id: str | None = None,
) -> list[ConceptGraphNode]:
    if school_id:
        from edu_cloud.services.knowledge_workflow import Question
        from fastapi import HTTPException
        q = (await db.execute(
            select(Question).where(
                Question.id == question_id,
                Question.school_id == school_id,
            )
        )).scalar_one_or_none()
        if not q:
            raise HTTPException(404, "Question not found")
    stmt = (
        select(ConceptGraphNode)
        .join(QuestionKnowledgePoint, QuestionKnowledgePoint.concept_id == ConceptGraphNode.id)
        .where(QuestionKnowledgePoint.question_id == question_id)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
