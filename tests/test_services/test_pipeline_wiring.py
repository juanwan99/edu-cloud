"""考后流水线接线测试 — 验证 stub 替换和 EventBus 集成。

D-03C：exam 不再直接 import pipeline，发布后处理经模块外编排服务
`edu_cloud.services.exam_publish_pipeline`。下面区分两层契约：
- exam → service（`ExamPublishService` 委托编排服务）
- service → pipeline（编排服务委托 pipeline owner 函数）
另含静态守护：exam 模块源码不得出现直接 pipeline import。
"""
import ast
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch


# ---- exam → 模块外编排服务（service-level 契约） ----

@pytest.mark.asyncio
async def test_publish_triggers_rankings(db):
    """publish 后 _calculate_rankings 委托编排服务 publish_rankings。"""
    with patch(
        "edu_cloud.services.exam_publish_pipeline.publish_rankings",
        new_callable=AsyncMock, return_value=5,
    ) as mock_rank:
        from edu_cloud.modules.exam.publish_service import ExamPublishService
        await ExamPublishService._calculate_rankings(db, "exam1", "school1")
        mock_rank.assert_called_once_with(db, exam_id="exam1", school_id="school1")


@pytest.mark.asyncio
async def test_publish_triggers_error_books(db):
    """publish 后 _update_error_books 委托编排服务 publish_error_books。"""
    with patch(
        "edu_cloud.services.exam_publish_pipeline.publish_error_books",
        new_callable=AsyncMock, return_value=3,
    ) as mock_eb:
        from edu_cloud.modules.exam.publish_service import ExamPublishService
        await ExamPublishService._update_error_books(db, "exam1", "school1")
        mock_eb.assert_called_once_with(db, exam_id="exam1", school_id="school1")


# ---- 模块外编排服务 → pipeline owner（service-level 契约） ----

@pytest.mark.asyncio
async def test_service_publish_rankings_delegates_to_pipeline(db):
    """编排服务 publish_rankings 委托 pipeline.generate_exam_snapshots 并回传计数。"""
    with patch(
        "edu_cloud.modules.pipeline.service.generate_exam_snapshots",
        new_callable=AsyncMock, return_value=5,
    ) as mock_snap:
        from edu_cloud.services.exam_publish_pipeline import publish_rankings
        count = await publish_rankings(db, exam_id="exam1", school_id="school1")
        mock_snap.assert_called_once_with(db, exam_id="exam1", school_id="school1")
        assert count == 5


@pytest.mark.asyncio
async def test_service_publish_error_books_delegates_to_pipeline(db):
    """编排服务 publish_error_books 委托 pipeline.populate_error_books 并回传计数。"""
    with patch(
        "edu_cloud.modules.pipeline.service.populate_error_books",
        new_callable=AsyncMock, return_value=3,
    ) as mock_eb:
        from edu_cloud.services.exam_publish_pipeline import publish_error_books
        count = await publish_error_books(db, exam_id="exam1", school_id="school1")
        mock_eb.assert_called_once_with(db, exam_id="exam1", school_id="school1")
        assert count == 3


# ---- 结构守护：exam 模块不得直接 import pipeline（D-03C 不变量） ----

def test_exam_module_has_no_direct_pipeline_import():
    """静态扫描 exam 模块源码，确认无 `edu_cloud.modules.pipeline` 直接 import。"""
    exam_dir = Path(__file__).resolve().parents[2] / "src" / "edu_cloud" / "modules" / "exam"
    offenders = []
    for py in exam_dir.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod == "edu_cloud.modules.pipeline" or mod.startswith(
                    "edu_cloud.modules.pipeline."
                ):
                    offenders.append(f"{py.name}:{node.lineno}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "edu_cloud.modules.pipeline" or alias.name.startswith(
                        "edu_cloud.modules.pipeline."
                    ):
                        offenders.append(f"{py.name}:{node.lineno}")
    assert not offenders, f"exam 模块仍直接 import pipeline: {offenders}"


# ---- 结构守护：pipeline 模块不得直接 import bank（D-03H 不变量） ----

def test_pipeline_module_has_no_direct_bank_import():
    """静态扫描 pipeline 模块源码，确认无 `edu_cloud.modules.bank` 直接 import。

    题库/错题本制品读写已上移模块外服务 `services.post_exam_bank_artifacts`
    （populate_bank_questions / populate_error_books 经 pipeline.service re-export），
    pipeline 模块自此不再直接依赖 bank，消除 `pipeline -> bank` 依赖边（D-03H）。
    """
    pipeline_dir = Path(__file__).resolve().parents[2] / "src" / "edu_cloud" / "modules" / "pipeline"
    offenders = []
    for py in pipeline_dir.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod == "edu_cloud.modules.bank" or mod.startswith(
                    "edu_cloud.modules.bank."
                ):
                    offenders.append(f"{py.name}:{node.lineno}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "edu_cloud.modules.bank" or alias.name.startswith(
                        "edu_cloud.modules.bank."
                    ):
                        offenders.append(f"{py.name}:{node.lineno}")
    assert not offenders, f"pipeline 模块仍直接 import bank: {offenders}"


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
    """on_exam_published handler 调用 mastery + patterns + adaptive 更新。"""
    with patch(
        "edu_cloud.modules.pipeline.service.update_knowledge_mastery",
        new_callable=AsyncMock, return_value=10,
    ) as mock_m, patch(
        "edu_cloud.modules.pipeline.service.update_error_patterns",
        new_callable=AsyncMock, return_value=5,
    ) as mock_p, patch(
        "edu_cloud.services.post_exam_adaptive.update_adaptive_mastery",
        new_callable=AsyncMock, return_value=3,
    ) as mock_a, patch(
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
        mock_a.assert_called_once()


@pytest.mark.asyncio
async def test_event_handler_ignores_missing_payload():
    """handler 缺少 exam_id 时安全退出。"""
    from edu_cloud.modules.pipeline import on_exam_published
    # 不应抛异常
    await on_exam_published({})
    await on_exam_published({"exam_id": "e1"})  # 缺 school_id
