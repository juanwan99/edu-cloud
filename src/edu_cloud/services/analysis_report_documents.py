"""分析报告文档创建编排（模块外应用服务）。

集中 studio 文档生命周期编排（create → reviewed → executed），使 analytics 不再
直接 import studio 模块实现 —— 拆掉 `analytics -> studio` 依赖边（D-03G）。studio
仍是文档状态机（`StudioService`）的 owner，本服务只负责跨模块编排。

对外契约与历史 `analytics_report_router.export_report` 内联逻辑一致：创建
`type=analysis_report` 文档（status=draft），按 draft → reviewed → executed 推进状态，
提交事务，返回已持久化的 `Document`。
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.document import Document

logger = logging.getLogger(__name__)


async def create_analysis_report_document(
    db: AsyncSession,
    *,
    title: str,
    content_json: dict,
    school_id: str,
    created_by: str,
) -> Document:
    """创建分析报告文档并推进至 executed 终态。

    模块内 `StudioService` 采用调用期局部 import，避免 services → modules 的导入期
    耦合，并让上游测试 patch 在编排层生效（与 `services.post_exam_pipeline` 同范式）。
    """
    from edu_cloud.modules.studio.service import StudioService

    svc = StudioService(db)
    doc = await svc.create_document(
        type="analysis_report",
        title=title,
        content_json=content_json,
        school_id=school_id,
        created_by=created_by,
    )
    # Studio 状态流转：draft → reviewed → executed
    await svc.transition_status(doc.id, "reviewed", school_id=school_id)
    await svc.transition_status(doc.id, "executed", school_id=school_id)
    await db.commit()
    logger.info(
        "analysis_report_document created: id=%s, school_id=%s, status=%s",
        doc.id, school_id, doc.status,
    )
    return doc
