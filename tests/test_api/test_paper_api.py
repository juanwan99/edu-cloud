import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import select

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
async def test_create_paper_creates_document_in_db(client, subject_teacher_headers, db):
    """T2: 创建论文时同时在 Studio 创建 Document 记录（跨会话验证落库）"""
    from edu_cloud.models.document import Document
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

    mock_svc = AsyncMock()
    mock_svc.create_paper.return_value = {
        "paper_id": "p-db-test", "stage": "intake", "status": "pending_intake",
        "title": "DB验证论文",
    }
    with patch("edu_cloud.api.studio.PaperService", return_value=mock_svc):
        resp = await client.post(
            "/api/v1/studio/paper/create",
            json={"budget_tier": "standard", "title": "DB验证论文"},
            headers=subject_teacher_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "document_id" in data
        assert data["paper_id"] == "p-db-test"

    # Cross-session verification: use a fresh session from the same engine to confirm commit happened
    # (uncommitted data would NOT be visible here; db.bind is the AsyncEngine)
    engine = db.bind
    fresh_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with fresh_factory() as fresh_db:
        doc = (await fresh_db.execute(
            select(Document).where(Document.id == data["document_id"])
        )).scalar_one_or_none()
        assert doc is not None, "Document not found in fresh session — commit may be missing"
        assert doc.type == "paper"
        assert doc.content_json["paper_id"] == "p-db-test"
        assert doc.source_context["paper_skill_id"] == "p-db-test"


@pytest.mark.asyncio
async def test_create_paper_non_subject_teacher_denied(client, teacher_headers):
    """T2: homeroom_teacher 没有 WRITE_PAPER 权限 → 403"""
    resp = await client.post(
        "/api/v1/studio/paper/create",
        json={"budget_tier": "standard"},
        headers=teacher_headers,
    )
    assert resp.status_code == 403
