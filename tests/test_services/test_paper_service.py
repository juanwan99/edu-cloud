import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from edu_cloud.services.paper_service import PaperService

@pytest.mark.asyncio
async def test_create_paper():
    """创建论文任务"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "data": {"paper_id": "p-123", "stage": "intake", "status": "pending_intake"}
    }

    with patch("edu_cloud.modules.paper.service.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_response
        MockClient.return_value = mock_client

        svc = PaperService()
        result = await svc.create_paper(budget_tier="standard", title="测试论文")
        assert result["paper_id"] == "p-123"
        assert result["stage"] == "intake"

@pytest.mark.asyncio
async def test_get_paper_status():
    """查询论文状态"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "data": {"id": "p-123", "stage": "brainstorm", "status": "brainstorming", "cost_yuan": 5.2}
    }

    with patch("edu_cloud.modules.paper.service.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.return_value = mock_response
        MockClient.return_value = mock_client

        svc = PaperService()
        result = await svc.get_status("p-123")
        assert result["stage"] == "brainstorm"
        assert result["cost_yuan"] == 5.2

@pytest.mark.asyncio
async def test_create_paper_failure():
    """paper-skill 不可用"""
    with patch("edu_cloud.modules.paper.service.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.side_effect = Exception("Connection refused")
        MockClient.return_value = mock_client

        svc = PaperService()
        result = await svc.create_paper(budget_tier="standard")
        assert "error" in result


@pytest.mark.asyncio
async def test_create_paper_success_false():
    """T2: paper-skill 返回 success=false"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": False,
        "error": "Invalid budget tier"
    }

    with patch("edu_cloud.modules.paper.service.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_response
        MockClient.return_value = mock_client

        svc = PaperService()
        result = await svc.create_paper(budget_tier="invalid")
        assert "error" in result
        assert "Invalid budget tier" in result["error"]


@pytest.mark.asyncio
async def test_get_status_failure():
    """T2: get_status 网络异常"""
    with patch("edu_cloud.modules.paper.service.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.side_effect = Exception("Timeout")
        MockClient.return_value = mock_client

        svc = PaperService()
        result = await svc.get_status("p-nonexistent")
        assert "error" in result


@pytest.mark.asyncio
async def test_get_status_success_false():
    """R2: get_status 返回 success=false"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": False,
        "error": "Paper not found"
    }

    with patch("edu_cloud.modules.paper.service.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.return_value = mock_response
        MockClient.return_value = mock_client

        svc = PaperService()
        result = await svc.get_status("p-nonexistent")
        assert "error" in result
        assert "Paper not found" in result["error"]
