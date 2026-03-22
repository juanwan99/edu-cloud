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
