import pytest
from edu_cloud.ai.tools.analytics import get_exam_scores, get_class_stats
from edu_cloud.ai.tool_context import ToolContext


def _ctx(db, school_id, class_ids=None):
    return ToolContext(db=db, school_id=school_id, user_id="u1", role="admin", class_ids=class_ids)


@pytest.mark.asyncio
async def test_get_exam_scores(db, seed_exam_with_results):
    exam_id = seed_exam_with_results["exam_id"]
    school_id = seed_exam_with_results["school_id"]
    result = await get_exam_scores({"exam_id": exam_id}, _ctx(db, school_id))
    assert result.success
    assert len(result.data["students"]) > 0
    assert "total_score" in result.data["students"][0]
    assert "stats" in result.data


@pytest.mark.asyncio
async def test_get_exam_scores_with_class_filter(db, seed_exam_with_results):
    exam_id = seed_exam_with_results["exam_id"]
    school_id = seed_exam_with_results["school_id"]
    class_id = seed_exam_with_results["class_id"]
    result = await get_exam_scores({"exam_id": exam_id}, _ctx(db, school_id, class_ids=[class_id]))
    assert result.success
    for s in result.data["students"]:
        assert s["class_id"] == class_id


@pytest.mark.asyncio
async def test_get_class_stats(db, seed_exam_with_results):
    exam_id = seed_exam_with_results["exam_id"]
    class_id = seed_exam_with_results["class_id"]
    result = await get_class_stats(
        {"exam_id": exam_id, "class_id": class_id},
        _ctx(db, seed_exam_with_results["school_id"]),
    )
    assert result.success
    assert "avg" in result.data
    assert "max" in result.data
    assert "min" in result.data
    assert "count" in result.data


# compare_classes → moved to analytics_compare.py (L2_analytics)
# get_student_profile → moved to students.py (L1_student)


@pytest.mark.asyncio
async def test_get_exam_scores_empty(db, seed_exam_with_results):
    result = await get_exam_scores({"exam_id": "nonexistent"}, _ctx(db, "none"))
    assert result.success
    assert result.data["students"] == []
    assert result.data["stats"]["count"] == 0


# ── Scope enforcement tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_class_stats_scope_denied(db, seed_exam_with_results):
    """get_class_stats rejects class_id outside caller's class_ids scope."""
    exam_id = seed_exam_with_results["exam_id"]
    class_id = seed_exam_with_results["class_id"]
    result = await get_class_stats(
        {"exam_id": exam_id, "class_id": class_id},
        _ctx(db, seed_exam_with_results["school_id"], class_ids=["other_class_id"]),
    )
    assert not result.success
    assert "无权" in result.error


@pytest.mark.asyncio
async def test_get_class_stats_scope_allowed(db, seed_exam_with_results):
    """get_class_stats allows class_id within caller's class_ids scope."""
    exam_id = seed_exam_with_results["exam_id"]
    class_id = seed_exam_with_results["class_id"]
    result = await get_class_stats(
        {"exam_id": exam_id, "class_id": class_id},
        _ctx(db, seed_exam_with_results["school_id"], class_ids=[class_id]),
    )
    assert result.success
    assert "avg" in result.data


@pytest.mark.asyncio
async def test_get_class_stats_scope_none_means_unrestricted(db, seed_exam_with_results):
    """class_ids=None means no restriction (admin/principal)."""
    exam_id = seed_exam_with_results["exam_id"]
    class_id = seed_exam_with_results["class_id"]
    result = await get_class_stats(
        {"exam_id": exam_id, "class_id": class_id},
        _ctx(db, seed_exam_with_results["school_id"], class_ids=None),
    )
    assert result.success
    assert "avg" in result.data


# student_profile scope tests → moved to students.py tests
