"""题库 + 错题本业务逻辑（从 exam-ai 迁入）。"""
import logging
from sqlalchemy import select, func
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
