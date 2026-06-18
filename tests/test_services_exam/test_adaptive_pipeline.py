"""验证 exam.published 事件触发 adaptive mastery 更新。"""
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_on_exam_published_calls_adaptive_mastery():
    """on_exam_published 应调用模块外服务 update_adaptive_mastery（D-03E）。"""
    with patch("edu_cloud.services.post_exam_adaptive.update_adaptive_mastery", new_callable=AsyncMock) as mock_adaptive, \
         patch("edu_cloud.modules.pipeline.service.update_knowledge_mastery", new_callable=AsyncMock, return_value=0), \
         patch("edu_cloud.modules.pipeline.service.update_error_patterns", new_callable=AsyncMock, return_value=0), \
         patch("edu_cloud.database.async_session") as mock_session_factory:

        mock_adaptive.return_value = 10

        mock_db = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_ctx

        from edu_cloud.modules.pipeline import on_exam_published
        await on_exam_published({"exam_id": "test-exam", "school_id": "test-school"})

        mock_adaptive.assert_called_once_with(mock_db, exam_id="test-exam", school_id="test-school")


@pytest.mark.asyncio
async def test_on_exam_published_missing_payload():
    """缺少 exam_id 或 school_id 时应直接返回。"""
    from edu_cloud.modules.pipeline import on_exam_published
    # 不应抛异常
    await on_exam_published({})
    await on_exam_published({"exam_id": "x"})
    await on_exam_published({"school_id": "x"})
