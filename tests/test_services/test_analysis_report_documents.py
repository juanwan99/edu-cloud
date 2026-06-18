"""D-03G: 分析报告文档创建编排服务（模块外）单测。

验证 `services.analysis_report_documents.create_analysis_report_document` 保留历史
`analytics_report_router.export_report` 内联行为：创建 `type=analysis_report` 文档、
`content_json` 结构不变、状态 draft → reviewed → executed、提交后持久化。
"""
import pytest
from sqlalchemy import select

from edu_cloud.models.document import Document
from edu_cloud.services.analysis_report_documents import (
    create_analysis_report_document,
)


def _content() -> dict:
    return {
        "report_type": "exam_analysis",
        "config": {"exam_ids": ["e1"], "metrics": ["summary", "segments"]},
        "sections": {"summary": {"avg": 88.5}, "segments": []},
    }


@pytest.mark.asyncio
async def test_create_analysis_report_document_reaches_executed(db):
    """draft → reviewed → executed 全流程，返回 executed 终态文档。"""
    doc = await create_analysis_report_document(
        db,
        title="期中考试分析报告",
        content_json=_content(),
        school_id="s1",
        created_by="creator1",
    )
    assert doc.type == "analysis_report"
    assert doc.status == "executed"
    assert doc.title == "期中考试分析报告"
    assert doc.version == 1


@pytest.mark.asyncio
async def test_create_analysis_report_document_preserves_content_json(db):
    """content_json 结构（report_type/config/sections）原样保留。"""
    content = _content()
    doc = await create_analysis_report_document(
        db,
        title="报告",
        content_json=content,
        school_id="s1",
        created_by="creator1",
    )
    assert doc.content_json == content


@pytest.mark.asyncio
async def test_create_analysis_report_document_persists(db):
    """提交事务后文档可被独立查询命中（持久化 + 隔离字段正确）。"""
    doc = await create_analysis_report_document(
        db,
        title="持久化报告",
        content_json=_content(),
        school_id="s2",
        created_by="creator2",
    )
    fetched = (
        await db.execute(select(Document).where(Document.id == doc.id))
    ).scalar_one()
    assert fetched.school_id == "s2"
    assert fetched.created_by == "creator2"
    assert fetched.type == "analysis_report"
    assert fetched.status == "executed"
