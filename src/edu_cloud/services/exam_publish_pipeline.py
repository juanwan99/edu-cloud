"""考后发布编排应用服务（模块外）。

集中编排 exam 发布后对 pipeline 模块的调用（排名快照 + 错题本），使 exam
模块不再直接 import pipeline —— 拆掉 exam → pipeline 依赖边及其参与的环
（D-03C）。pipeline 仍是排名快照/错题本步骤的 owner，本服务只负责跨模块编排。

对外契约：返回各步骤生成数量，exam `ExamPublishService` 改调本服务即可，
行为与历史在 publish_service 内联调用 pipeline 完全一致。
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def publish_rankings(db: AsyncSession, *, exam_id: str, school_id: str) -> int:
    """排名计算 — 委托 pipeline 的 generate_exam_snapshots（含排名+知识点维度）。

    模块内函数采用调用期局部 import，既避免 services → modules 的导入期耦合，
    也让上游对 `pipeline.service.generate_exam_snapshots` 的测试 patch 在编排层生效。
    """
    from edu_cloud.modules.pipeline.service import generate_exam_snapshots

    count = await generate_exam_snapshots(db, exam_id=exam_id, school_id=school_id)
    logger.info("publish_rankings: exam_id=%s, snapshots=%d", exam_id, count)
    return count


async def publish_error_books(db: AsyncSession, *, exam_id: str, school_id: str) -> int:
    """错题更新 — 委托 pipeline 的 populate_error_books。"""
    from edu_cloud.modules.pipeline.service import populate_error_books

    count = await populate_error_books(db, exam_id=exam_id, school_id=school_id)
    logger.info("publish_error_books: exam_id=%s, errors=%d", exam_id, count)
    return count
