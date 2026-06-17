"""考后编排应用服务（模块外）。

集中编排 pipeline 模块的冷数据步骤与 analytics 的考后分析预计算，使 pipeline
模块不再直接 import analytics —— 拆掉 pipeline → analytics 依赖边及其参与的环
（D-03B）。pipeline 仍是自身冷数据步骤的 owner，本服务只负责跨模块编排。

对外契约：返回值与历史 `run_full_pipeline` 一致（冷数据各步骤 + `exam_analysis`），
外部调用点（pipeline router / exam service / worker / seed_demo）改调本服务即可。
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def run_post_exam_pipeline(db: AsyncSession, *, exam_id: str, school_id: str) -> dict:
    """考后完整编排：先跑 pipeline 冷数据，再跑 analytics 考后分析预计算。

    模块内函数采用调用期局部 import，既避免 services → modules 的导入期耦合，
    也让上游对 `pipeline.service.run_full_pipeline` 的测试 patch 在编排层生效。
    """
    from edu_cloud.modules.pipeline.service import run_full_pipeline
    from edu_cloud.modules.analytics.pipeline_service import compute_exam_analysis

    results = await run_full_pipeline(db, exam_id=exam_id, school_id=school_id)
    results["exam_analysis"] = await compute_exam_analysis(
        db, exam_id=exam_id, school_id=school_id,
    )
    logger.info("post_exam_pipeline orchestrated: exam=%s, results=%s", exam_id, results)
    return results
