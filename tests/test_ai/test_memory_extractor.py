"""Tests for MemoryExtractor — extract + persist cross-session memories."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from edu_cloud.ai.memory_extractor import MemoryExtractor
from edu_cloud.ai.llm_adapter import LLMResponse, TokenUsage
from edu_cloud.ai.schemas import Message
from edu_cloud.ai.memory_store import MemoryStore


@pytest.fixture
def mock_adapter():
    adapter = MagicMock()
    adapter.chat = AsyncMock(return_value=LLMResponse(
        content='[{"type": "entity", "entity_type": "student", "entity_id": "stu-1", '
                '"facts": {"math_mastery": 0.4}}, '
                '{"type": "episode", "summary": "讨论了学生数学成绩"}]',
        stop_reason="end_turn",
        usage=TokenUsage(100, 50),
    ))
    return adapter


@pytest.fixture
def mock_store():
    store = MagicMock(spec=MemoryStore)
    store.upsert_entity = AsyncMock()
    store.cleanup_episodes = AsyncMock(return_value=0)
    return store


class TestMemoryExtractor:
    @pytest.mark.asyncio
    async def test_extract_and_persist(self, mock_adapter, mock_store):
        extractor = MemoryExtractor(store=mock_store)
        messages = [
            Message(role="user", content="张三的数学成绩怎么样？"),
            Message(role="assistant", content="张三数学掌握率 40%，建议加强函数图像"),
        ]
        await extractor.extract_and_persist(
            db=MagicMock(), messages=messages, adapter=mock_adapter,
            school_id="sch-1", user_id="u-1", session_id="sess-1",
        )
        assert mock_store.upsert_entity.call_count >= 1
        calls = mock_store.upsert_entity.call_args_list
        entity_types = [c.kwargs.get("entity_type") or c.args[2] for c in calls]
        assert "student" in entity_types or "session_episode" in entity_types

    @pytest.mark.asyncio
    async def test_empty_messages_skips(self, mock_adapter, mock_store):
        extractor = MemoryExtractor(store=mock_store)
        await extractor.extract_and_persist(
            db=MagicMock(), messages=[], adapter=mock_adapter,
            school_id="sch-1", user_id="u-1", session_id="sess-1",
        )
        mock_adapter.chat.assert_not_called()
        mock_store.upsert_entity.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_failure_graceful(self, mock_store):
        adapter = MagicMock()
        adapter.chat = AsyncMock(side_effect=Exception("LLM unavailable"))
        extractor = MemoryExtractor(store=mock_store)
        await extractor.extract_and_persist(
            db=MagicMock(),
            messages=[Message(role="user", content="test")],
            adapter=adapter,
            school_id="sch-1", user_id="u-1", session_id="sess-1",
        )
        mock_store.upsert_entity.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_json_graceful(self, mock_store):
        adapter = MagicMock()
        adapter.chat = AsyncMock(return_value=LLMResponse(
            content="not valid json",
            stop_reason="end_turn",
            usage=TokenUsage(100, 50),
        ))
        extractor = MemoryExtractor(store=mock_store)
        await extractor.extract_and_persist(
            db=MagicMock(),
            messages=[Message(role="user", content="test")],
            adapter=adapter,
            school_id="sch-1", user_id="u-1", session_id="sess-1",
        )
        mock_store.upsert_entity.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_called(self, mock_adapter, mock_store):
        extractor = MemoryExtractor(store=mock_store)
        await extractor.extract_and_persist(
            db=MagicMock(),
            messages=[Message(role="user", content="test")],
            adapter=mock_adapter,
            school_id="sch-1", user_id="u-1", session_id="sess-1",
        )
        mock_store.cleanup_episodes.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_db_commit(self, mock_adapter, mock_store):
        """MemoryExtractor must NOT call db.commit() — API layer owns transaction boundary."""
        db = MagicMock()
        db.commit = AsyncMock()
        extractor = MemoryExtractor(store=mock_store)
        await extractor.extract_and_persist(
            db=db,
            messages=[Message(role="user", content="test")],
            adapter=mock_adapter,
            school_id="sch-1", user_id="u-1", session_id="sess-1",
        )
        db.commit.assert_not_called()
