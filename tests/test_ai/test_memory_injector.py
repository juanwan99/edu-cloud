"""Tests for MemoryInjector — TDD test suite."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from edu_cloud.ai.memory_injector import MemoryInjector
from edu_cloud.ai.memory_store import MemoryStore
from edu_cloud.models.memory import EntityMemory, ProjectState


@pytest.fixture
def mock_store():
    store = MagicMock(spec=MemoryStore)
    store.get_entities = AsyncMock(return_value=[])
    store.get_active_projects = AsyncMock(return_value=[])
    return store


class TestMemoryInjector:
    @pytest.mark.asyncio
    async def test_no_memory_returns_empty(self, mock_store):
        injector = MemoryInjector(store=mock_store, max_tokens=2000)
        result = await injector.build_context(
            db=MagicMock(), school_id="sch-1", user_id="u-1",
            role="teacher", class_ids=["c1"],
        )
        assert result == ""

    @pytest.mark.asyncio
    async def test_entity_memory_formatted(self, mock_store):
        mem = MagicMock(spec=EntityMemory)
        mem.entity_type = "student"
        mem.entity_id = "stu-1"
        mem.facts = {"math_mastery": 0.4, "weakness": "函数图像"}
        mock_store.get_entities = AsyncMock(return_value=[mem])

        injector = MemoryInjector(store=mock_store, max_tokens=2000)
        result = await injector.build_context(
            db=MagicMock(), school_id="sch-1", user_id="u-1",
            role="principal",  # principal has full access, no class_ids restriction
        )
        assert "student" in result
        assert "stu-1" in result
        assert "函数图像" in result

    @pytest.mark.asyncio
    async def test_project_state_included(self, mock_store):
        proj = MagicMock(spec=ProjectState)
        proj.project_type = "paper"
        proj.project_id = "p1"
        proj.state = {"topic": "深度学习", "checkpoint": "writing"}
        proj.status = "active"
        mock_store.get_active_projects = AsyncMock(return_value=[proj])

        injector = MemoryInjector(store=mock_store, max_tokens=2000)
        result = await injector.build_context(
            db=MagicMock(), school_id="sch-1", user_id="u-1",
            role="teacher",
        )
        assert "paper" in result
        assert "深度学习" in result

    @pytest.mark.asyncio
    async def test_token_budget_truncation(self, mock_store):
        mems = []
        for i in range(50):
            m = MagicMock(spec=EntityMemory)
            m.entity_type = "student"
            m.entity_id = f"s-{i}"
            m.facts = {"detail": f"这是一段很长的描述内容用来测试token预算控制机制第{i}条" * 5}
            mems.append(m)
        mock_store.get_entities = AsyncMock(return_value=mems)

        injector = MemoryInjector(store=mock_store, max_tokens=500)
        result = await injector.build_context(
            db=MagicMock(), school_id="sch-1", user_id="u-1",
            role="principal",  # full access
        )
        assert len(result) < 500 * 4

    @pytest.mark.asyncio
    async def test_episodes_limited(self, mock_store):
        episodes = []
        for i in range(10):
            m = MagicMock(spec=EntityMemory)
            m.entity_type = "session_episode"
            m.entity_id = f"ep-{i}"
            m.facts = {"summary": f"Episode {i}"}
            episodes.append(m)
        mock_store.get_entities = AsyncMock(return_value=episodes)

        injector = MemoryInjector(store=mock_store, max_tokens=5000)
        result = await injector.build_context(
            db=MagicMock(), school_id="sch-1", user_id="u-1",
            role="teacher",
        )
        assert result.count("Episode") <= 5

    @pytest.mark.asyncio
    async def test_teacher_scope_skips_student_injection(self, mock_store):
        """Teachers with class_ids but no student_ids should skip student memory injection."""
        async def mock_get_entities(db, school_id, entity_type, **kwargs):
            if entity_type == "student":
                m = MagicMock(spec=EntityMemory)
                m.entity_type = "student"
                m.entity_id = "stu-1"
                m.facts = {"math": 0.4}
                return [m]
            return []
        mock_store.get_entities = AsyncMock(side_effect=mock_get_entities)

        injector = MemoryInjector(store=mock_store, max_tokens=2000)
        result = await injector.build_context(
            db=MagicMock(), school_id="sch-1", user_id="u-1",
            role="subject_teacher", class_ids=["c1"],
            # student_ids=None — teacher doesn't have student-level scope
        )
        # Student entity type should be skipped (continue branch)
        student_calls = [c for c in mock_store.get_entities.call_args_list
                        if len(c.args) >= 3 and c.args[2] == "student"]
        assert len(student_calls) == 0, "Should skip student query when teacher has class_ids but no student_ids"
        assert "stu-1" not in result
