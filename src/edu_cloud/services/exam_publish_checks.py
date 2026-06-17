"""考试发布前置检查应用服务（模块外）。

集中执行 exam 发布前对 grading 模块的前置条件查询（阅卷完成度 + 高危质量问题），
使 exam 模块不再直接 import grading —— 拆掉 exam -> grading 依赖边及其参与的
4 个依赖环（D-03D）。grading 仍是阅卷任务 / 质量检查记录的 owner，本服务只负责
跨模块的发布前置校验。

对外契约：前置条件不满足时抛 `StateError`，异常类型与错误信息语义与历史在
`ExamPublishService.publish` 内联检查完全一致，exam 改调本服务即可，行为不变。
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.services.exceptions import StateError

logger = logging.getLogger(__name__)


async def ensure_grading_complete(db: AsyncSession, *, exam_id: str) -> None:
    """前置条件：该考试的所有阅卷任务已完成。

    grading 模型采用调用期局部 import，避免 services -> modules 的导入期耦合，
    也让上游对 `grading.models` 的测试 patch 在编排层生效。存在未完成阅卷任务时
    抛 `StateError`，错误信息语义与历史内联检查一致。
    """
    from edu_cloud.modules.grading.models import GradingAssignment

    stmt = select(GradingAssignment).where(GradingAssignment.exam_id == exam_id)
    result = await db.execute(stmt)
    assignments = list(result.scalars().all())
    incomplete = [a for a in assignments if a.status != "completed"]
    if incomplete:
        raise StateError(f"{len(incomplete)} grading assignments not completed")


async def ensure_no_high_severity_issues(db: AsyncSession, *, exam_id: str) -> None:
    """前置条件：该考试无 HIGH severity 质量问题。

    存在 high severity 质量检查记录时抛 `StateError`，错误信息语义与历史内联检查一致。
    """
    from edu_cloud.modules.grading.models import GradingQualityCheck

    stmt = select(GradingQualityCheck).where(
        GradingQualityCheck.exam_id == exam_id,
        GradingQualityCheck.severity == "high",
    )
    result = await db.execute(stmt)
    high_issues = list(result.scalars().all())
    if high_issues:
        raise StateError(f"{len(high_issues)} high-severity quality issues unresolved")
