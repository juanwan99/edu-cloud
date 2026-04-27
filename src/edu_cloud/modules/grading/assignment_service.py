"""阅卷任务分配 Service。"""
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.grading.models import GradingAssignment

_TZ = timezone(timedelta(hours=8))


def _now():
    return datetime.now(_TZ)


class GradingAssignmentService:
    @staticmethod
    async def assign_block(
        db: AsyncSession, *, exam_id: str, subject_id: str,
        question_ids: list[str], teacher_id: str, school_id: str,
        total_count: int,
    ) -> GradingAssignment:
        from edu_cloud.services.exceptions import ConflictError
        existing_stmt = select(GradingAssignment).where(
            GradingAssignment.exam_id == exam_id,
            GradingAssignment.subject_id == subject_id,
            GradingAssignment.assigned_to == teacher_id,
            GradingAssignment.status != "completed",
        )
        existing_result = await db.execute(existing_stmt)
        for a in existing_result.scalars():
            overlap = set(a.question_ids) & set(question_ids)
            if overlap:
                raise ConflictError(
                    f"Questions {overlap} already assigned to {a.assigned_to}"
                )
        assignment = GradingAssignment(
            exam_id=exam_id, subject_id=subject_id,
            question_ids=question_ids, assigned_to=teacher_id,
            total_count=total_count, school_id=school_id,
        )
        db.add(assignment)
        await db.flush()
        return assignment

    @staticmethod
    async def auto_assign(
        db: AsyncSession, *, exam_id: str, subject_id: str,
        question_ids: list[str], teacher_ids: list[str], school_id: str,
        total_count_per_question: int,
    ) -> list[GradingAssignment]:
        if not teacher_ids or not question_ids:
            return []
        n = len(teacher_ids)
        base = total_count_per_question // n if total_count_per_question else 0
        remainder = total_count_per_question % n if total_count_per_question else 0
        assignments = []
        for q_id in question_ids:
            for i, tid in enumerate(teacher_ids):
                count = base + (1 if i < remainder else 0)
                a = GradingAssignment(
                    exam_id=exam_id, subject_id=subject_id,
                    question_ids=[q_id], assigned_to=tid,
                    total_count=count, school_id=school_id,
                )
                assignments.append(a)
        db.add_all(assignments)
        await db.flush()
        return assignments

    @staticmethod
    async def update_progress(
        db: AsyncSession, assignment_id: str, graded_count: int
    ) -> GradingAssignment:
        assignment = await db.get(GradingAssignment, assignment_id)
        assignment.graded_count = graded_count
        if assignment.total_count == 0:
            assignment.status = "completed"
            assignment.completed_at = _now()
            return assignment
        if assignment.status == "pending" and graded_count > 0:
            assignment.status = "in_progress"
            assignment.started_at = _now()
        if graded_count >= assignment.total_count:
            assignment.status = "completed"
            assignment.completed_at = _now()
        return assignment

    @staticmethod
    async def list_assignments(
        db: AsyncSession, exam_id: str, *, school_id: str, assigned_to: str | None = None,
    ) -> list[GradingAssignment]:
        stmt = select(GradingAssignment).where(
            GradingAssignment.exam_id == exam_id,
            GradingAssignment.school_id == school_id,
        )
        if assigned_to:
            stmt = stmt.where(GradingAssignment.assigned_to == assigned_to)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_progress(db: AsyncSession, exam_id: str, *, school_id: str) -> dict:
        assignments = await GradingAssignmentService.list_assignments(db, exam_id, school_id=school_id)
        total_papers = sum(a.total_count for a in assignments)
        graded_papers = sum(a.graded_count for a in assignments)
        return {
            "total_assignments": len(assignments),
            "completed": sum(1 for a in assignments if a.status == "completed"),
            "in_progress": sum(1 for a in assignments if a.status == "in_progress"),
            "pending": sum(1 for a in assignments if a.status == "pending"),
            "total_papers": total_papers,
            "graded_papers": graded_papers,
            "progress_pct": round(graded_papers / max(total_papers, 1) * 100, 1),
            "by_teacher": [
                {
                    "teacher_id": a.assigned_to,
                    "status": a.status,
                    "graded": a.graded_count,
                    "total": a.total_count,
                    "questions": a.question_ids,
                }
                for a in assignments
            ],
        }
