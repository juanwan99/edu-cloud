"""学生画像查询（统一到 ConceptGraphNode）。"""
import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.services.profile_workflow import ConceptGraphNode
from edu_cloud.modules.profile.models import StudentExamSnapshot, StudentKnowledgeMastery, StudentErrorPattern

logger = logging.getLogger(__name__)


async def get_student_trend(
    db: AsyncSession, *, student_id: str, school_id: str,
    subject_code: str | None = None, limit: int = 10,
) -> list[StudentExamSnapshot]:
    stmt = (
        select(StudentExamSnapshot)
        .where(StudentExamSnapshot.student_id == student_id, StudentExamSnapshot.school_id == school_id)
    )
    if subject_code:
        stmt = stmt.where(StudentExamSnapshot.subject_code == subject_code)
    stmt = stmt.order_by(StudentExamSnapshot.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_student_knowledge_map(
    db: AsyncSession, *, student_id: str, school_id: str,
    course_code: str | None = None,
) -> list[StudentKnowledgeMastery]:
    stmt = (
        select(StudentKnowledgeMastery)
        .where(StudentKnowledgeMastery.student_id == student_id, StudentKnowledgeMastery.school_id == school_id)
    )
    if course_code:
        stmt = stmt.join(ConceptGraphNode, ConceptGraphNode.id == StudentKnowledgeMastery.concept_id)
        stmt = stmt.where(ConceptGraphNode.course_code == course_code)
    stmt = stmt.order_by(StudentKnowledgeMastery.mastery_level)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_class_knowledge_weakness(
    db: AsyncSession, *, school_id: str,
    class_student_ids: list[str], course_code: str | None = None,
    top_n: int = 5,
) -> list[dict]:
    stmt = (
        select(
            StudentKnowledgeMastery.concept_id,
            ConceptGraphNode.name,
            ConceptGraphNode.id,
            func.avg(StudentKnowledgeMastery.mastery_level).label("avg_mastery"),
            func.count().label("student_count"),
        )
        .join(ConceptGraphNode, ConceptGraphNode.id == StudentKnowledgeMastery.concept_id)
        .where(
            StudentKnowledgeMastery.student_id.in_(class_student_ids),
            StudentKnowledgeMastery.school_id == school_id,
        )
    )
    if course_code:
        stmt = stmt.where(ConceptGraphNode.course_code == course_code)

    stmt = (
        stmt
        .group_by(StudentKnowledgeMastery.concept_id, ConceptGraphNode.name, ConceptGraphNode.id)
        .order_by(func.avg(StudentKnowledgeMastery.mastery_level))
        .limit(top_n)
    )
    result = await db.execute(stmt)
    return [
        {
            "concept_id": row[0], "name": row[1], "code": row[2],
            "avg_mastery": round(float(row[3]), 4), "student_count": row[4],
        }
        for row in result.all()
    ]


async def get_student_error_pattern(
    db: AsyncSession, *, student_id: str, school_id: str,
    subject_code: str | None = None,
) -> list[StudentErrorPattern]:
    stmt = (
        select(StudentErrorPattern)
        .where(StudentErrorPattern.student_id == student_id, StudentErrorPattern.school_id == school_id)
    )
    if subject_code:
        stmt = stmt.where(StudentErrorPattern.subject_code == subject_code)
    result = await db.execute(stmt)
    return list(result.scalars().all())
