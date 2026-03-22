"""Studio REST API tests: templates, document CRUD, status transitions, auth."""

import pytest


@pytest.fixture
async def other_school_doc_id(db):
    """在另一个学校创建文档，用于跨校访问测试。"""
    from edu_cloud.models.school import RegisteredSchool
    from edu_cloud.models.user import User
    from edu_cloud.models.document import Document

    other_school = RegisteredSchool(
        name="其他校", code="OTHER01", district="其他区", api_key_hash="x"
    )
    db.add(other_school)
    await db.flush()

    other_user = User(username="other_teacher", display_name="李老师")
    other_user.set_password("123456")
    db.add(other_user)
    await db.flush()

    doc = Document(
        type="report",
        title="其他校文档",
        content_json={"test": True},
        school_id=other_school.id,
        created_by=other_user.id,
    )
    db.add(doc)
    await db.commit()
    return doc.id


@pytest.mark.asyncio
async def test_get_templates(client, teacher_headers):
    resp = await client.get("/api/v1/studio/templates", headers=teacher_headers)
    assert resp.status_code == 200
    templates = resp.json()
    assert len(templates) >= 1
    assert any(t["key"] == "class_report" for t in templates)


@pytest.mark.asyncio
async def test_list_documents_empty(client, teacher_headers):
    resp = await client.get("/api/v1/studio/documents", headers=teacher_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_and_get_document(client, teacher_headers):
    create_resp = await client.post(
        "/api/v1/studio/documents",
        json={
            "type": "report",
            "title": "测试报告",
            "content_json": {
                "overview": {"title": "概况", "content": "测试内容"}
            },
        },
        headers=teacher_headers,
    )
    assert create_resp.status_code == 201
    doc_id = create_resp.json()["id"]

    get_resp = await client.get(
        f"/api/v1/studio/documents/{doc_id}", headers=teacher_headers
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["title"] == "测试报告"


@pytest.mark.asyncio
async def test_update_document(client, teacher_headers):
    resp = await client.post(
        "/api/v1/studio/documents",
        json={
            "type": "report",
            "title": "测试",
            "content_json": {"body": "v1"},
        },
        headers=teacher_headers,
    )
    doc_id = resp.json()["id"]

    update_resp = await client.patch(
        f"/api/v1/studio/documents/{doc_id}",
        json={
            "content_json": {"body": "v2"},
            "change_summary": "修改正文",
        },
        headers=teacher_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["version"] == 2


@pytest.mark.asyncio
async def test_transition_status(client, teacher_headers):
    resp = await client.post(
        "/api/v1/studio/documents",
        json={
            "type": "report",
            "title": "测试",
            "content_json": {},
        },
        headers=teacher_headers,
    )
    doc_id = resp.json()["id"]

    tr_resp = await client.post(
        f"/api/v1/studio/documents/{doc_id}/transition",
        json={"status": "reviewed"},
        headers=teacher_headers,
    )
    assert tr_resp.status_code == 200
    assert tr_resp.json()["status"] == "reviewed"


@pytest.mark.asyncio
async def test_studio_requires_auth(client):
    resp = await client.get("/api/v1/studio/templates")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_cross_school_access_denied(client, teacher_headers, other_school_doc_id):
    resp = await client.get(
        f"/api/v1/studio/documents/{other_school_doc_id}",
        headers=teacher_headers,
    )
    assert resp.status_code == 403


# ── N1 fix: 无权限角色不能访问文档端点 ────────────────────────────


@pytest.mark.asyncio
async def test_observer_cannot_access_documents(client, observer_headers):
    """N1: observer 角色没有 GENERATE_REPORT 权限 → 403"""
    resp = await client.get("/api/v1/studio/documents", headers=observer_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_observer_cannot_get_document(client, observer_headers, teacher_headers):
    """N1: observer 不能读取文档详情"""
    # teacher 先创建文档
    create_resp = await client.post(
        "/api/v1/studio/documents",
        json={"type": "report", "title": "权限测试", "content_json": {}},
        headers=teacher_headers,
    )
    doc_id = create_resp.json()["id"]

    # observer 尝试获取 → 403
    resp = await client.get(
        f"/api/v1/studio/documents/{doc_id}", headers=observer_headers
    )
    assert resp.status_code == 403


# ── N4 fix: body 缺字段返回 422 ───────────────────────────────────


@pytest.mark.asyncio
async def test_create_document_missing_fields(client, teacher_headers):
    """N4: 缺少 type/title → 422"""
    resp = await client.post(
        "/api/v1/studio/documents",
        json={"title": "只有标题"},
        headers=teacher_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_document_missing_content_json(client, teacher_headers):
    """N4: PATCH 缺少 content_json → 422"""
    # 先创建
    resp = await client.post(
        "/api/v1/studio/documents",
        json={"type": "report", "title": "测试", "content_json": {}},
        headers=teacher_headers,
    )
    doc_id = resp.json()["id"]

    # 缺 content_json
    resp = await client.patch(
        f"/api/v1/studio/documents/{doc_id}",
        json={"change_summary": "无内容"},
        headers=teacher_headers,
    )
    assert resp.status_code == 422
