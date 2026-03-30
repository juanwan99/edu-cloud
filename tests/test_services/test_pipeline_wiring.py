"""考后流水线接线测试 — 验证 stub 替换和 EventBus 集成。"""
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_publish_triggers_rankings(db):
    """publish 后 _calculate_rankings 调用 generate_exam_snapshots。"""
    with patch(
        "edu_cloud.modules.pipeline.service.generate_exam_snapshots",
        new_callable=AsyncMock, return_value=5,
    ) as mock_snap:
        from edu_cloud.modules.exam.publish_service import ExamPublishService
        await ExamPublishService._calculate_rankings(db, "exam1", "school1")
        mock_snap.assert_called_once_with(db, exam_id="exam1", school_id="school1")


@pytest.mark.asyncio
async def test_publish_triggers_error_books(db):
    """publish 后 _update_error_books 调用 populate_error_books。"""
    with patch(
        "edu_cloud.modules.pipeline.service.populate_error_books",
        new_callable=AsyncMock, return_value=3,
    ) as mock_eb:
        from edu_cloud.modules.exam.publish_service import ExamPublishService
        await ExamPublishService._update_error_books(db, "exam1", "school1")
        mock_eb.assert_called_once_with(db, exam_id="exam1", school_id="school1")


@pytest.mark.asyncio
async def test_event_bus_handler_registered():
    """exam.published 事件有 handler 注册。"""
    from edu_cloud.core.events import event_bus
    import edu_cloud.modules.pipeline  # noqa: F401 — 触发 handler 注册
    handlers = event_bus._handlers.get("exam.published", [])
    assert len(handlers) >= 1
    assert any(h.__name__ == "on_exam_published" for h in handlers)


@pytest.mark.asyncio
async def test_event_handler_calls_mastery_and_patterns():
    """on_exam_published handler 调用 mastery + patterns 更新。"""
    with patch(
        "edu_cloud.modules.pipeline.service.update_knowledge_mastery",
        new_callable=AsyncMock, return_value=10,
    ) as mock_m, patch(
        "edu_cloud.modules.pipeline.service.update_error_patterns",
        new_callable=AsyncMock, return_value=5,
    ) as mock_p, patch(
        "edu_cloud.database.async_session",
    ) as mock_session:
        # Mock the async context manager
        mock_db = AsyncMock()
        mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.return_value.__aexit__ = AsyncMock(return_value=False)

        from edu_cloud.modules.pipeline import on_exam_published
        await on_exam_published({"exam_id": "e1", "school_id": "s1"})

        mock_m.assert_called_once()
        mock_p.assert_called_once()


@pytest.mark.asyncio
async def test_event_handler_ignores_missing_payload():
    """handler 缺少 exam_id 时安全退出。"""
    from edu_cloud.modules.pipeline import on_exam_published
    # 不应抛异常
    await on_exam_published({})
    await on_exam_published({"exam_id": "e1"})  # 缺 school_id
