import pytest
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_create_paper_requires_write_paper_permission(client):
    """未认证用户不能创建论文"""
    resp = await client.post("/api/v1/studio/paper/create", json={"budget_tier": "standard"})
    assert resp.status_code in (401, 403)

@pytest.mark.asyncio
async def test_create_paper_success(client, subject_teacher_headers):
    """subject_teacher 可以创建论文"""
    mock_svc = AsyncMock()
    mock_svc.create_paper.return_value = {
        "paper_id": "p-test-123", "stage": "intake", "status": "pending_intake"
    }
    with patch("edu_cloud.api.studio.PaperService", return_value=mock_svc):
        resp = await client.post(
            "/api/v1/studio/paper/create",
            json={"budget_tier": "standard", "title": "测试论文"},
            headers=subject_teacher_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "paper_id" in data

@pytest.mark.asyncio
async def test_get_paper_status_auth_required(client):
    """未认证不能查询论文进度"""
    resp = await client.get("/api/v1/studio/paper/p-123/status")
    assert resp.status_code in (401, 403)

@pytest.mark.asyncio
async def test_get_paper_status_success(client, subject_teacher_headers):
    """认证用户可查询论文进度"""
    mock_svc = AsyncMock()
    mock_svc.get_status.return_value = {
        "id": "p-123", "stage": "brainstorm", "status": "brainstorming", "cost_yuan": 5.2
    }
    with patch("edu_cloud.api.studio.PaperService", return_value=mock_svc):
        resp = await client.get(
            "/api/v1/studio/paper/p-123/status",
            headers=subject_teacher_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["stage"] == "brainstorm"
