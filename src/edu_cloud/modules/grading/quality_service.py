"""质量抽检 Service。"""
import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.grading.models import GradingQualityCheck


class QualityCheckService:
    @staticmethod
    async def create_sampling_checks(
        db: AsyncSession, *, exam_id: str, subject_id: str,
        source_data: list[dict], rate: float = 0.1, school_id: str,
    ) -> list[GradingQualityCheck]:
        sample_size = max(1, int(len(source_data) * rate))
        sampled = random.sample(source_data, min(sample_size, len(source_data)))
        checks = []
        for item in sampled:
            check = GradingQualityCheck(
                exam_id=exam_id, subject_id=subject_id,
                question_id=item["question_id"],
                check_type="sampling",
                original_result_id=item.get("result_id"),
                original_grader_id=item.get("grader_id"),
                original_score=item["score"],
                school_id=school_id,
            )
            checks.append(check)
        db.add_all(checks)
        await db.flush()
        return checks

    @staticmethod
    async def review_check(
        db: AsyncSession, *, check_id: str, checker_id: str,
        check_score: float, max_score: float, comment: str | None = None,
    ) -> GradingQualityCheck:
        check = await db.get(GradingQualityCheck, check_id)
        check.checker_id = checker_id
        check.check_score = check_score
        check.deviation = abs(check_score - check.original_score)
        check.comment = comment
        check.status = "reviewed"
        if max_score > 0:
            pct = check.deviation / max_score * 100
            if pct <= 10:
                check.severity = "low"
            elif pct <= 20:
                check.severity = "med"
            else:
                check.severity = "high"
        return check

    @staticmethod
    async def get_quality_report(db: AsyncSession, exam_id: str, *, school_id: str) -> dict:
        stmt = select(GradingQualityCheck).where(
            GradingQualityCheck.exam_id == exam_id,
            GradingQualityCheck.school_id == school_id,
        )
        result = await db.execute(stmt)
        checks = list(result.scalars().all())
        reviewed = [c for c in checks if c.status == "reviewed"]
        return {
            "total_checks": len(checks),
            "reviewed": len(reviewed),
            "pending": len(checks) - len(reviewed),
            "avg_deviation": (
                round(sum(c.deviation or 0 for c in reviewed) / max(len(reviewed), 1), 2)
            ),
            "high_severity_count": sum(1 for c in reviewed if c.severity == "high"),
            "has_blocking_issues": any(c.severity == "high" for c in reviewed),
        }
