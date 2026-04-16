"""成绩查看服务。"""
import statistics
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.exam.models import JointExamStudentResult
from edu_cloud.services.exceptions import NotFoundError


class ResultsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_rankings(
        self, exam_id: str, subject_code: str | None = None,
    ) -> list[dict]:
        if subject_code:
            q = (
                select(JointExamStudentResult)
                .where(JointExamStudentResult.joint_exam_id == exam_id)
                .where(JointExamStudentResult.subject_code == subject_code)
                .order_by(JointExamStudentResult.total_score.desc())
            )
            results = (await self.db.execute(q)).scalars().all()
            return [
                {"rank": i + 1, "student_name": r.student_name,
                 "student_number": r.student_number, "school_id": r.school_id,
                 "total_score": r.total_score}
                for i, r in enumerate(results)
            ]
        else:
            q = (
                select(
                    JointExamStudentResult.student_number,
                    JointExamStudentResult.student_name,
                    JointExamStudentResult.school_id,
                    func.sum(JointExamStudentResult.total_score).label("total"),
                )
                .where(JointExamStudentResult.joint_exam_id == exam_id)
                .group_by(
                    JointExamStudentResult.student_number,
                    JointExamStudentResult.student_name,
                    JointExamStudentResult.school_id,
                )
                .order_by(func.sum(JointExamStudentResult.total_score).desc())
            )
            rows = (await self.db.execute(q)).all()
            return [
                {"rank": i + 1, "student_name": r.student_name,
                 "student_number": r.student_number, "school_id": r.school_id,
                 "total_score": float(r.total)}
                for i, r in enumerate(rows)
            ]

    async def get_school_comparison(self, exam_id: str) -> list[dict]:
        q = (
            select(
                JointExamStudentResult.school_id,
                JointExamStudentResult.subject_code,
                func.avg(JointExamStudentResult.total_score).label("avg"),
                func.max(JointExamStudentResult.total_score).label("max"),
                func.count().label("count"),
            )
            .where(JointExamStudentResult.joint_exam_id == exam_id)
            .group_by(
                JointExamStudentResult.school_id,
                JointExamStudentResult.subject_code,
            )
        )
        rows = (await self.db.execute(q)).all()

        result = []
        for row in rows:
            scores_q = (
                select(JointExamStudentResult.total_score)
                .where(JointExamStudentResult.joint_exam_id == exam_id)
                .where(JointExamStudentResult.school_id == row.school_id)
                .where(JointExamStudentResult.subject_code == row.subject_code)
            )
            scores = [s for (s,) in (await self.db.execute(scores_q)).all()]
            median = statistics.median(scores) if scores else 0.0

            result.append({
                "school_id": row.school_id,
                "subject_code": row.subject_code,
                "avg_score": round(float(row.avg), 2),
                "max_score": float(row.max),
                "median_score": median,
                "student_count": row.count,
            })
        return result

    async def get_student_detail(
        self, exam_id: str, student_number: str, school_id: str | None = None,
    ) -> dict:
        q = (
            select(JointExamStudentResult)
            .where(JointExamStudentResult.joint_exam_id == exam_id)
            .where(JointExamStudentResult.student_number == student_number)
        )
        if school_id:
            q = q.where(JointExamStudentResult.school_id == school_id)
        results = (await self.db.execute(q)).scalars().all()
        if not results:
            raise NotFoundError(f"Student '{student_number}' not found in exam")

        subjects_with_rank = []
        for r in results:
            rank_q = (
                select(func.count())
                .select_from(JointExamStudentResult)
                .where(JointExamStudentResult.joint_exam_id == exam_id)
                .where(JointExamStudentResult.subject_code == r.subject_code)
                .where(JointExamStudentResult.total_score > r.total_score)
            )
            higher_count = (await self.db.execute(rank_q)).scalar() or 0
            subjects_with_rank.append({
                "subject_code": r.subject_code, "total_score": r.total_score,
                "rank": higher_count + 1,
                "detail_scores": r.detail_scores,
            })

        return {
            "student_name": results[0].student_name,
            "student_number": student_number,
            "school_id": results[0].school_id,
            "subjects": subjects_with_rank,
        }
