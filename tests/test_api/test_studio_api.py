"""Studio REST API tests: templates, document CRUD, status transitions, auth."""

import pytest


@pytest.fixture
async def other_school_doc_id(db):
    """在另一个学校创建文档，用于跨校访问测试。"""
    from edu_cloud.models.school import School
    from edu_cloud.models.user import User
    from edu_cloud.models.document import Document

    other_school = School(
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


# ── R3 fix: 补全 PATCH/transition 权限 + transition 缺字段 ────────


@pytest.mark.asyncio
async def test_observer_cannot_patch_document(client, observer_headers, teacher_headers):
    """R3: observer 不能 PATCH 文档"""
    resp = await client.post(
        "/api/v1/studio/documents",
        json={"type": "report", "title": "权限测试", "content_json": {}},
        headers=teacher_headers,
    )
    doc_id = resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/studio/documents/{doc_id}",
        json={"content_json": {"hacked": True}},
        headers=observer_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_observer_cannot_transition_document(client, observer_headers, teacher_headers):
    """R3: observer 不能转换文档状态"""
    resp = await client.post(
        "/api/v1/studio/documents",
        json={"type": "report", "title": "权限测试", "content_json": {}},
        headers=teacher_headers,
    )
    doc_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/studio/documents/{doc_id}/transition",
        json={"status": "reviewed"},
        headers=observer_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_transition_missing_status_returns_422(client, teacher_headers):
    """R3: transition 缺少 status → 422"""
    resp = await client.post(
        "/api/v1/studio/documents",
        json={"type": "report", "title": "测试", "content_json": {}},
        headers=teacher_headers,
    )
    doc_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/studio/documents/{doc_id}/transition",
        json={},
        headers=teacher_headers,
    )
    assert resp.status_code == 422


# ── TG-001: 通知 transition 测试 ─────────────────────────────────────


@pytest.mark.asyncio
async def test_notification_reviewed_to_executed_blocked(client, teacher_headers):
    """TG-001: 通知文档 reviewed → executed 必须返回 409（必须先走审批流）"""
    # 创建通知文档
    resp = await client.post(
        "/api/v1/studio/documents",
        json={"type": "notification", "title": "测试通知", "content_json": {}},
        headers=teacher_headers,
    )
    assert resp.status_code == 201
    doc_id = resp.json()["id"]

    # 转到 reviewed
    tr_resp = await client.post(
        f"/api/v1/studio/documents/{doc_id}/transition",
        json={"status": "reviewed"},
        headers=teacher_headers,
    )
    assert tr_resp.status_code == 200

    # 尝试直接从 reviewed 跳到 executed → 应被阻断（StateError → 409）
    exec_resp = await client.post(
        f"/api/v1/studio/documents/{doc_id}/transition",
        json={"status": "executed"},
        headers=teacher_headers,
    )
    assert exec_resp.status_code == 409


@pytest.mark.asyncio
async def test_notification_approved_to_executed_succeeds(client, teacher_headers, db):
    """TG-001: 通知文档从 approved 状态转到 executed 成功"""
    from edu_cloud.models.document import Document
    from sqlalchemy import select

    # 创建通知文档
    resp = await client.post(
        "/api/v1/studio/documents",
        json={"type": "notification", "title": "审批后通知", "content_json": {}},
        headers=teacher_headers,
    )
    assert resp.status_code == 201
    doc_id = resp.json()["id"]

    # 直接修改数据库状态到 approved（模拟已过审批流）
    doc = await db.get(Document, doc_id)
    doc.status = "approved"
    await db.commit()

    # 从 approved 转到 executed → 应成功
    exec_resp = await client.post(
        f"/api/v1/studio/documents/{doc_id}/transition",
        json={"status": "executed"},
        headers=teacher_headers,
    )
    assert exec_resp.status_code == 200
    assert exec_resp.json()["status"] == "executed"


@pytest.mark.asyncio
async def test_report_reviewed_to_executed_succeeds(client, teacher_headers):
    """TG-001: 非通知文档（report）reviewed → executed 不受审批流限制"""
    # 创建 report 文档
    resp = await client.post(
        "/api/v1/studio/documents",
        json={"type": "report", "title": "测试报告", "content_json": {}},
        headers=teacher_headers,
    )
    assert resp.status_code == 201
    doc_id = resp.json()["id"]

    # 转到 reviewed
    tr_resp = await client.post(
        f"/api/v1/studio/documents/{doc_id}/transition",
        json={"status": "reviewed"},
        headers=teacher_headers,
    )
    assert tr_resp.status_code == 200

    # 从 reviewed 转到 executed → 应成功（report 不需要审批）
    exec_resp = await client.post(
        f"/api/v1/studio/documents/{doc_id}/transition",
        json={"status": "executed"},
        headers=teacher_headers,
    )
    assert exec_resp.status_code == 200
    assert exec_resp.json()["status"] == "executed"


@pytest.mark.asyncio
async def test_notification_executed_requires_send_permission(
    client, subject_teacher_headers, teacher_headers, db
):
    """TG-001: subject_teacher 没有 GENERATE_NOTIFICATION 权限 → 403"""
    from edu_cloud.models.document import Document

    # teacher (homeroom_teacher) 先创建通知文档并设置为 approved
    resp = await client.post(
        "/api/v1/studio/documents",
        json={"type": "notification", "title": "权限测试通知", "content_json": {}},
        headers=teacher_headers,
    )
    assert resp.status_code == 201
    doc_id = resp.json()["id"]

    # 直接设为 approved 状态
    doc = await db.get(Document, doc_id)
    doc.status = "approved"
    await db.commit()

    # subject_teacher 尝试执行 → 403（没有 GENERATE_NOTIFICATION 权限）
    exec_resp = await client.post(
        f"/api/v1/studio/documents/{doc_id}/transition",
        json={"status": "executed"},
        headers=subject_teacher_headers,
    )
    assert exec_resp.status_code == 403


@pytest.mark.asyncio
async def test_notification_pending_creates_approval_flow(client, teacher_headers, db):
    """TG-001/CB-3: 通知文档 transition 到 pending 时自动创建 ApprovalFlow；
    空审批人列表 → flow 立即 approved，文档自动推进到 approved"""
    from edu_cloud.models.approval import ApprovalFlow
    from sqlalchemy import select

    # 创建通知文档
    resp = await client.post(
        "/api/v1/studio/documents",
        json={"type": "notification", "title": "待审批通知", "content_json": {}},
        headers=teacher_headers,
    )
    assert resp.status_code == 201
    doc_id = resp.json()["id"]

    # 转到 reviewed
    tr_resp = await client.post(
        f"/api/v1/studio/documents/{doc_id}/transition",
        json={"status": "reviewed"},
        headers=teacher_headers,
    )
    assert tr_resp.status_code == 200

    # 转到 pending → 应自动创建 ApprovalFlow
    # CB-3: 空审批人 → flow.status="approved" → 文档自动推进到 approved
    pending_resp = await client.post(
        f"/api/v1/studio/documents/{doc_id}/transition",
        json={"status": "pending"},
        headers=teacher_headers,
    )
    assert pending_resp.status_code == 200
    # 空审批人时文档自动推进到 approved
    assert pending_resp.json()["status"] == "approved"

    # 验证 ApprovalFlow 已在数据库中创建，且状态为 approved（空审批人自动审批）
    flows = (await db.execute(
        select(ApprovalFlow).where(ApprovalFlow.document_id == doc_id)
    )).scalars().all()
    assert len(flows) == 1
    assert flows[0].status == "approved"


@pytest.mark.asyncio
async def test_grade_leader_cannot_execute_notification(
    client, grade_leader_headers, db
):
    """TG-4: grade_leader 有 GENERATE_NOTIFICATION 但无 SEND_NOTIFICATION → 403"""
    from edu_cloud.models.document import Document

    # grade_leader 自己创建通知文档（grade_leader 有 GENERATE_NOTIFICATION）
    resp = await client.post(
        "/api/v1/studio/documents",
        json={"type": "notification", "title": "SEND测试", "content_json": {}},
        headers=grade_leader_headers,
    )
    assert resp.status_code == 201
    doc_id = resp.json()["id"]

    # 手动设为 approved
    doc = await db.get(Document, doc_id)
    doc.status = "approved"
    await db.commit()

    # grade_leader 尝试 executed → 403 (有 GENERATE_NOTIFICATION，无 SEND_NOTIFICATION)
    exec_resp = await client.post(
        f"/api/v1/studio/documents/{doc_id}/transition",
        json={"status": "executed"},
        headers=grade_leader_headers,
    )
    assert exec_resp.status_code == 403
    assert "SEND_NOTIFICATION" in exec_resp.json()["detail"]
