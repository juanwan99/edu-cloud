import pytest
from edu_cloud.ai.tools.actions import generate_report, generate_comment
from edu_cloud.ai.tool_context import ToolContext


def _ctx(db, school_id, user_id="test_user", class_ids=None):
    return ToolContext(db=db, school_id=school_id, user_id=user_id, role="admin", class_ids=class_ids)


@pytest.mark.asyncio
async def test_generate_report(db, seed_exam_with_results):
    from edu_cloud.models.document import Document

    result = await generate_report(
        {"template": "class_report",
         "context": {"exam_id": seed_exam_with_results["exam_id"], "class_id": seed_exam_with_results["class_id"]}},
        _ctx(db, seed_exam_with_results["school_id"], class_ids=[seed_exam_with_results["class_id"]]),
    )
    assert result.success
    assert result.data["status"] == "draft"
    assert result.data["title"] is not None

    doc = await db.get(Document, result.data["document_id"])
    assert doc is not None
    assert doc.type == "report"


@pytest.mark.asyncio
async def test_generate_report_unknown_template(db, seed_exam_with_results):
    result = await generate_report(
        {"template": "nonexistent", "context": {}},
        _ctx(db, seed_exam_with_results["school_id"]),
    )
    assert not result.success
    assert "未知模板" in result.error


@pytest.mark.asyncio
async def test_generate_report_missing_context(db, seed_exam_with_results):
    result = await generate_report(
        {"template": "class_report", "context": {}},
        _ctx(db, seed_exam_with_results["school_id"]),
    )
    assert not result.success
    assert "缺少必需上下文" in result.error


@pytest.mark.asyncio
async def test_generate_comment(db, seed_exam_with_results):
    result = await generate_comment(
        {"student_number": "T000"},
        _ctx(db, seed_exam_with_results["school_id"], class_ids=[seed_exam_with_results["class_id"]]),
    )
    assert result.success
    assert result.data["type"] == "comment"


# ── F4 fix: content_json 结构断言 + 学生不存在 ────────────────────


@pytest.mark.asyncio
async def test_generate_report_content_json_has_sections(db, seed_exam_with_results):
    """F4: content_json 按模板生成所有 section"""
    from edu_cloud.models.document import Document

    result = await generate_report(
        {"template": "class_report",
         "context": {"exam_id": seed_exam_with_results["exam_id"],
                     "class_id": seed_exam_with_results["class_id"]}},
        _ctx(db, seed_exam_with_results["school_id"], class_ids=[seed_exam_with_results["class_id"]]),
    )
    assert result.success
    assert result.data["sections"] == ["overview", "subject_analysis", "student_tiers", "suggestions"]

    doc = await db.get(Document, result.data["document_id"])
    for key in ["overview", "subject_analysis", "student_tiers", "suggestions"]:
        assert key in doc.content_json
        assert "title" in doc.content_json[key]
        assert "content" in doc.content_json[key]


@pytest.mark.asyncio
async def test_generate_comment_student_not_found(db, seed_exam_with_results):
    """F4: 学生不存在 → 返回 error"""
    result = await generate_comment(
        {"student_number": "NONEXISTENT"},
        _ctx(db, seed_exam_with_results["school_id"], class_ids=[seed_exam_with_results["class_id"]]),
    )
    assert not result.success
    assert "不存在" in result.error


# ── N2 fix: generate_comment class_ids scope ──────────────────────


@pytest.mark.asyncio
async def test_generate_comment_cross_class_denied(db, seed_exam_with_results):
    """N2: 教师只能为自己班级的学生生成评语"""
    result = await generate_comment(
        {"student_number": "T000"},
        _ctx(db, seed_exam_with_results["school_id"], class_ids=["other-class-id"]),
    )
    assert not result.success
    assert "不存在" in result.error


@pytest.mark.asyncio
async def test_generate_comment_empty_class_ids_denied(db, seed_exam_with_results):
    """N2 R3: 空 class_ids=[] 不能绕过 scope 检查"""
    result = await generate_comment(
        {"student_number": "T000"},
        _ctx(db, seed_exam_with_results["school_id"], class_ids=[]),
    )
    assert not result.success
