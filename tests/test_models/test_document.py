from edu_cloud.models.document import Document, DocumentVersion
from edu_cloud.models.approval import ApprovalFlow, ApprovalStep


def test_document_fields():
    cols = {c.name for c in Document.__table__.columns}
    assert "type" in cols
    assert "title" in cols
    assert "status" in cols
    assert "content_json" in cols
    assert "content_html" in cols
    assert "pdf_url" in cols
    assert "source_context" in cols
    assert "ai_session_id" in cols
    assert "created_by" in cols
    assert "approved_by" in cols
    assert "school_id" in cols
    assert "version" in cols


def test_document_status_default():
    """新文档默认 draft 状态"""
    d = Document(type="report", title="测试", school_id="s1", created_by="u1")
    assert d.status == "draft"
    assert d.version == 1


def test_document_version_fields():
    cols = {c.name for c in DocumentVersion.__table__.columns}
    assert "document_id" in cols
    assert "version" in cols
    assert "content_json" in cols
    assert "edited_by" in cols
    assert "change_summary" in cols


def test_approval_flow_fields():
    cols = {c.name for c in ApprovalFlow.__table__.columns}
    assert "document_id" in cols
    assert "chain_type" in cols
    assert "current_step" in cols
    assert "status" in cols


def test_approval_step_fields():
    cols = {c.name for c in ApprovalStep.__table__.columns}
    assert "flow_id" in cols
    assert "approver_id" in cols
    assert "step_order" in cols
    assert "status" in cols
    assert "comment" in cols


# ── F5 fix: 模型持久化测试 ──────────────────────────────────────


import pytest


@pytest.mark.asyncio
async def test_document_persists_with_defaults(db, seed_teacher):
    """F5: Document 最小字段集插入成功，默认值持久化正确"""
    from edu_cloud.models.user_role import UserRole
    from sqlalchemy import select

    role = (
        await db.execute(
            select(UserRole).where(UserRole.user_id == seed_teacher.id)
        )
    ).scalar_one()

    doc = Document(
        type="report", title="持久化测试",
        school_id=role.school_id, created_by=seed_teacher.id,
    )
    db.add(doc)
    await db.flush()

    # 从 DB 重新读取
    loaded = await db.get(Document, doc.id)
    assert loaded is not None
    assert loaded.status == "draft"
    assert loaded.version == 1
    assert loaded.content_json is None  # nullable 字段可缺失
    assert loaded.pdf_url is None


@pytest.mark.asyncio
async def test_document_version_persists_with_valid_parent(db, seed_teacher):
    """F5: DocumentVersion 能正确关联到已有 Document"""
    from edu_cloud.models.user_role import UserRole
    from sqlalchemy import select, func

    role = (
        await db.execute(
            select(UserRole).where(UserRole.user_id == seed_teacher.id)
        )
    ).scalar_one()

    doc = Document(
        type="report", title="版本FK测试",
        school_id=role.school_id, created_by=seed_teacher.id,
    )
    db.add(doc)
    await db.flush()

    ver = DocumentVersion(
        document_id=doc.id, version=1,
        content_json={"old": "data"},
        edited_by=seed_teacher.id,
        change_summary="initial",
    )
    db.add(ver)
    await db.flush()

    count = (await db.execute(
        select(func.count()).select_from(DocumentVersion)
        .where(DocumentVersion.document_id == doc.id)
    )).scalar()
    assert count == 1
