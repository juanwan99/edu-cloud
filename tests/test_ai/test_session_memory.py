import pytest
from unittest.mock import AsyncMock
from edu_cloud.ai.session_memory import SessionMemoryExtractor, MemoryEntry
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMResponse, TokenUsage
from edu_cloud.ai.schemas import Message
from edu_cloud.models.agent_memory import AgentMemory


def test_memory_entry_fields():
    entry = MemoryEntry(
        memory_type="finding",
        content="二班数学函数掌握度仅 38%",
        entity_type="class",
        entity_id="C002",
    )
    assert entry.memory_type == "finding"
    assert entry.entity_type == "class"


def test_agent_memory_model_has_fields():
    columns = {c.name for c in AgentMemory.__table__.columns}
    assert "school_id" in columns
    assert "session_id" in columns
    assert "user_id" in columns
    assert "memory_type" in columns
    assert "content" in columns
    assert "entity_type" in columns
    assert "entity_id" in columns
    assert "is_active" in columns


@pytest.mark.asyncio
async def test_extract_returns_memories():
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    adapter.chat = AsyncMock(return_value=LLMResponse(
        content='[{"type":"finding","content":"二班数学持续退步","entity_type":"class","entity_id":"C002"}]',
        usage=TokenUsage(100, 50),
    ))

    extractor = SessionMemoryExtractor()
    messages = [
        Message(role="user", content="分析三年级"),
        Message(role="assistant", content="二班数学退步严重"),
    ]
    entries = await extractor.extract(messages, adapter)
    assert len(entries) >= 1
    assert entries[0].memory_type == "finding"


@pytest.mark.asyncio
async def test_extract_handles_bad_json():
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    adapter.chat = AsyncMock(return_value=LLMResponse(
        content="This is not valid JSON",
        usage=TokenUsage(10, 5),
    ))

    extractor = SessionMemoryExtractor()
    entries = await extractor.extract([Message(role="user", content="test")], adapter)
    assert entries == []


def test_parse_fenced_json():
    """F003: markdown fenced JSON should be parsed correctly."""
    entries = SessionMemoryExtractor._parse(
        '```json\n[{"type":"finding","content":"test finding"}]\n```'
    )
    assert len(entries) == 1
    assert entries[0].content == "test finding"


def test_parse_non_list_json():
    """F003: top-level non-list JSON returns empty."""
    entries = SessionMemoryExtractor._parse('{"type": "finding"}')
    assert entries == []
