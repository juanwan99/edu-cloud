import pytest
from edu_cloud.ai.tools.actions import generate_report, generate_comment


@pytest.mark.asyncio
async def test_generate_report(db, seed_exam_with_results):
    from edu_cloud.models.document import Document

    result = await generate_report(
        template="class_report",
        context={"exam_id": seed_exam_with_results["exam_id"], "class_id": seed_exam_with_results["class_id"]},
        _db=db,
        _school_id=seed_exam_with_results["school_id"],
        _user_id="test_user",
        _class_ids=[seed_exam_with_results["class_id"]],
    )
    assert "document_id" in result
    assert result["status"] == "draft"
    assert result["title"] is not None

    doc = await db.get(Document, result["document_id"])
    assert doc is not None
    assert doc.type == "report"


@pytest.mark.asyncio
async def test_generate_report_unknown_template(db, seed_exam_with_results):
    result = await generate_report(
        template="nonexistent",
        context={},
        _db=db, _school_id=seed_exam_with_results["school_id"],
        _user_id="test", _class_ids=[],
    )
    assert "error" in result


@pytest.mark.asyncio
async def test_generate_report_missing_context(db, seed_exam_with_results):
    result = await generate_report(
        template="class_report",
        context={},
        _db=db, _school_id=seed_exam_with_results["school_id"],
        _user_id="test", _class_ids=[],
    )
    assert "error" in result
    assert "缺少必需上下文" in result["error"]


@pytest.mark.asyncio
async def test_generate_comment(db, seed_exam_with_results):
    result = await generate_comment(
        student_number="T000",
        _db=db,
        _school_id=seed_exam_with_results["school_id"],
        _user_id="test_user",
        _class_ids=[seed_exam_with_results["class_id"]],
    )
    assert "document_id" in result
    assert result["type"] == "comment"
