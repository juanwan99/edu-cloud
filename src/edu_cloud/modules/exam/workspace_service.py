"""工作台数据查询服务：左栏上下文树 + 考试仪表板。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.exam import Exam, ExamResult
from edu_cloud.models.class_group import ClassGroup
from edu_cloud.models.student import Student


class WorkspaceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_context_tree(self, school_id: str | None, scope: dict) -> dict:
        """Get left panel context data (filtered by scope).

        Returns classes and recent exams visible to the current user.
        """
        if not school_id:
            return {"classes": [], "exams": []}

        # Classes — filtered by scope
        q = select(ClassGroup).where(ClassGroup.school_id == school_id)
        if scope.get("class_ids"):
            q = q.where(ClassGroup.id.in_(scope["class_ids"]))
        classes = (await self.db.execute(q)).scalars().all()

        # Recent exams (most recent 20)
        q = (
            select(Exam)
            .where(Exam.school_id == school_id)
            .order_by(Exam.created_at.desc())
            .limit(20)
        )
        exams = (await self.db.execute(q)).scalars().all()

        return {
            "classes": [
                {"id": c.id, "name": c.name, "grade": c.grade}
                for c in classes
            ],
            "exams": [
                {
                    "id": e.id,
                    "name": e.name,
                    "status": e.status,
                    "subject_code": e.subject_code,
                    "semester": e.semester,
                }
                for e in exams
            ],
        }

    async def get_exam_dashboard(
        self, exam_id: str, school_id: str | None, scope: dict
    ) -> dict:
        """Get exam dashboard data (score distribution + stats), filtered by scope."""
        if not school_id:
            return {"stats": {}, "score_distribution": []}

        q = select(ExamResult).where(
            ExamResult.exam_id == exam_id,
            ExamResult.school_id == school_id,
        )
        if scope.get("class_ids"):
            q = q.join(Student, ExamResult.student_id == Student.id).where(
                Student.class_id.in_(scope["class_ids"])
            )
        results = (await self.db.execute(q)).scalars().all()

        scores = [r.total_score for r in results]
        if not scores:
            return {"stats": {}, "score_distribution": []}

        # Score distribution by percentage ranges (adapts to different max scores)
        exam = await self.db.get(Exam, exam_id)
        max_s = (exam.max_score if exam and exam.max_score else 100)
        bins = [0, max_s * 0.4, max_s * 0.6, max_s * 0.7, max_s * 0.8, max_s * 0.9, max_s + 0.1]
        labels = ["<40%", "40-59%", "60-69%", "70-79%", "80-89%", "90%+"]
        distribution = []
        for i in range(len(bins) - 1):
            count = len([s for s in scores if bins[i] <= s < bins[i + 1]])
            distribution.append({"range": labels[i], "count": count})

        sorted_scores = sorted(scores)
        n = len(sorted_scores)
        if n % 2 == 1:
            median = sorted_scores[n // 2]
        else:
            median = (sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2

        return {
            "stats": {
                "count": n,
                "avg": round(sum(scores) / n, 1),
                "max": max(scores),
                "min": min(scores),
                "median": median,
            },
            "score_distribution": distribution,
        }
