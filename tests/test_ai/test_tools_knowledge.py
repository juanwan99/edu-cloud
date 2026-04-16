import pytest
from unittest.mock import patch, MagicMock
from edu_cloud.ai.tools.knowledge import search_curriculum, search_textbook, search_gaokao, get_concept_info
from edu_cloud.ai.tool_context import ToolContext, ToolResult


def _ctx():
    return ToolContext(db=None, school_id="s1", user_id="u1", role="admin")


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.search_curriculum.return_value = [
        {"module": "分子与细胞", "text": "阐明基因表达的过程", "requirement_id": "req:001"}
    ]
    store.search_knowledge.return_value = [
        {"id": "BK_002", "content": "基因表达包括转录和翻译", "category": "process"}
    ]
    store.get_concept.return_value = {
        "canonical_name": "基因表达",
        "description": "DNA→RNA→蛋白质",
        "l0_ids": ["BK_002"],
    }
    store.search_gaokao.return_value = [
        {"exam_id": "GK_2024_BJ", "year": 2024, "region": "北京", "question_count": 8}
    ]
    return store

@pytest.mark.asyncio
async def test_search_curriculum_tool(mock_store):
    with patch("edu_cloud.ai.tools.knowledge.knowledge_store", mock_store):
        result = await search_curriculum({"keyword": "基因表达"}, _ctx())
        assert result.success
        assert len(result.data["results"]) >= 1
        assert "基因表达" in result.data["results"][0]["text"]

@pytest.mark.asyncio
async def test_search_textbook_tool(mock_store):
    with patch("edu_cloud.ai.tools.knowledge.knowledge_store", mock_store):
        result = await search_textbook({"keyword": "基因表达"}, _ctx())
        assert result.success
        assert len(result.data["blocks"]) >= 1

@pytest.mark.asyncio
async def test_get_concept_info_tool(mock_store):
    with patch("edu_cloud.ai.tools.knowledge.knowledge_store", mock_store):
        result = await get_concept_info({"concept_name": "基因表达"}, _ctx())
        assert result.success
        assert result.data["concept"]["canonical_name"] == "基因表达"

@pytest.mark.asyncio
async def test_get_concept_not_found(mock_store):
    mock_store.get_concept.return_value = None
    with patch("edu_cloud.ai.tools.knowledge.knowledge_store", mock_store):
        result = await get_concept_info({"concept_name": "不存在"}, _ctx())
        assert not result.success
        assert "未找到概念" in result.error

@pytest.mark.asyncio
async def test_search_gaokao_tool(mock_store):
    with patch("edu_cloud.ai.tools.knowledge.knowledge_store", mock_store):
        result = await search_gaokao({"year": 2024, "region": "北京"}, _ctx())
        assert result.success
        assert len(result.data["exams"]) >= 1
        assert result.data["exams"][0]["region"] == "北京"

@pytest.mark.asyncio
async def test_search_gaokao_no_filter(mock_store):
    with patch("edu_cloud.ai.tools.knowledge.knowledge_store", mock_store):
        result = await search_gaokao({}, _ctx())
        assert result.success
