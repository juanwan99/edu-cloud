import pytest
from unittest.mock import patch, AsyncMock, MagicMock

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
    with patch("edu_cloud.modules.studio.router.PaperService", return_value=mock_svc):
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
    with patch("edu_cloud.modules.studio.router.PaperService", return_value=mock_svc):
        resp = await client.get(
            "/api/v1/studio/paper/p-123/status",
            headers=subject_teacher_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["stage"] == "brainstorm"


# ── T1: paper 模板可见性 ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_paper_template_visible_to_subject_teacher(client, subject_teacher_headers):
    """T1: paper 模板只对 subject_teacher 可见"""
    resp = await client.get("/api/v1/studio/templates", headers=subject_teacher_headers)
    assert resp.status_code == 200
    templates = resp.json()
    assert any(t["key"] == "paper" for t in templates)


@pytest.mark.asyncio
async def test_paper_template_not_visible_to_teacher(client, teacher_headers):
    """T1: homeroom_teacher 看不到 paper 模板"""
    resp = await client.get("/api/v1/studio/templates", headers=teacher_headers)
    assert resp.status_code == 200
    templates = resp.json()
    assert not any(t["key"] == "paper" for t in templates)


# ── T2: Document 落库验证 + 权限拒绝 ────────────────────────────

@pytest.mark.asyncio
async def test_create_paper_creates_document_in_db(client, subject_teacher_headers):
    """T2: 创建论文时同时在 Studio 创建 Document 记录（通过 API 验证可观测行为）"""
    mock_svc = AsyncMock()
    mock_svc.create_paper.return_value = {
        "paper_id": "p-db-test", "stage": "intake", "status": "pending_intake",
        "title": "DB验证论文",
    }
    with patch("edu_cloud.modules.studio.router.PaperService", return_value=mock_svc):
        resp = await client.post(
            "/api/v1/studio/paper/create",
            json={"budget_tier": "standard", "title": "DB验证论文"},
            headers=subject_teacher_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "document_id" in data
        assert data["paper_id"] == "p-db-test"

    # API-level verification: GET /documents should return the newly created paper document
    # This proves the endpoint created the Document AND committed the transaction,
    # because GET /documents goes through a separate request cycle.
    list_resp = await client.get("/api/v1/studio/documents", headers=subject_teacher_headers)
    assert list_resp.status_code == 200
    docs = list_resp.json()
    paper_docs = [d for d in docs if d["type"] == "paper"]
    assert len(paper_docs) >= 1, "Paper document not found via GET /documents — create_document or commit may be missing"
    assert paper_docs[0]["id"] == data["document_id"]
    assert paper_docs[0]["content_json"]["paper_id"] == "p-db-test"


@pytest.mark.asyncio
async def test_create_paper_homeroom_teacher_allowed(client, teacher_headers):
    """T2: homeroom_teacher 现在有 WRITE_PAPER（教师基线权限），可创建论文。"""
    resp = await client.post(
        "/api/v1/studio/paper/create",
        json={"budget_tier": "standard"},
        headers=teacher_headers,
    )
    # 权限通过（非 403），paper-skill 可能不在线导致超时/500，但权限层面不拦截
    assert resp.status_code != 403
