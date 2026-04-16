"""Tests for memory_read / memory_write Agent tools."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from edu_cloud.ai.tool_context import ToolContext, ToolResult


class TestMemoryReadTool:
    @pytest.mark.asyncio
    async def test_read_entity(self):
        from edu_cloud.ai.tools.memory_tools import memory_read

        ctx = MagicMock(spec=ToolContext)
        ctx.school_id = "sch-1"
        ctx.db = MagicMock()
        ctx.data_scope = None  # no DataScope

        with patch("edu_cloud.ai.tools.memory_tools._store") as mock_store:
            mock_entity = MagicMock()
            mock_entity.entity_id = "stu-1"
            mock_entity.facts = {"math": 0.4}
            mock_store.get_entities = AsyncMock(return_value=[mock_entity])

            result = await memory_read(
                {"entity_type": "student", "entity_ids": ["stu-1"]},
                ctx,
            )
            assert result.success
            assert len(result.data) == 1

    @pytest.mark.asyncio
    async def test_read_with_data_scope(self):
        from edu_cloud.ai.tools.memory_tools import memory_read

        ctx = MagicMock(spec=ToolContext)
        ctx.school_id = "sch-1"
        ctx.db = MagicMock()
        ctx.data_scope = MagicMock()
        ctx.data_scope.visible_student_ids = ["stu-1", "stu-2"]

        with patch("edu_cloud.ai.tools.memory_tools._store") as mock_store:
            mock_store.get_entities = AsyncMock(return_value=[])
            result = await memory_read({"entity_type": "student"}, ctx)
            assert result.success
            # Should pass visible_student_ids from DataScope
            call_kwargs = mock_store.get_entities.call_args
            assert call_kwargs.kwargs.get("visible_student_ids") == ["stu-1", "stu-2"]

    @pytest.mark.asyncio
    async def test_read_all_of_type(self):
        from edu_cloud.ai.tools.memory_tools import memory_read

        ctx = MagicMock(spec=ToolContext)
        ctx.school_id = "sch-1"
        ctx.db = MagicMock()
        ctx.data_scope = None

        with patch("edu_cloud.ai.tools.memory_tools._store") as mock_store:
            mock_store.get_entities = AsyncMock(return_value=[])
            result = await memory_read({"entity_type": "student"}, ctx)
            assert result.success


class TestMemoryWriteTool:
    @pytest.mark.asyncio
    async def test_write_entity(self):
        from edu_cloud.ai.tools.memory_tools import memory_write

        ctx = MagicMock(spec=ToolContext)
        ctx.school_id = "sch-1"
        ctx.db = MagicMock()

        with patch("edu_cloud.ai.tools.memory_tools._store") as mock_store:
            mock_result = MagicMock()
            mock_result.entity_id = "stu-1"
            mock_result.facts = {"math": 0.7}
            mock_store.upsert_entity = AsyncMock(return_value=mock_result)

            result = await memory_write(
                {"entity_type": "student", "entity_id": "stu-1",
                 "facts": {"math": 0.7}},
                ctx,
            )
            assert result.success

    @pytest.mark.asyncio
    async def test_write_empty_facts(self):
        from edu_cloud.ai.tools.memory_tools import memory_write

        ctx = MagicMock(spec=ToolContext)
        ctx.school_id = "sch-1"
        ctx.db = MagicMock()

        result = await memory_write(
            {"entity_type": "student", "entity_id": "stu-1", "facts": {}},
            ctx,
        )
        assert not result.success
        assert "空" in result.error


class TestToolRegistration:
    def test_tools_registered(self):
        from edu_cloud.ai.registry import tools
        import edu_cloud.ai.tools.memory_tools  # noqa: F401

        assert tools.get("memory_read") is not None
        assert tools.get("memory_write") is not None

    def test_memory_write_not_readonly(self):
        from edu_cloud.ai.registry import tools
        import edu_cloud.ai.tools.memory_tools  # noqa: F401

        spec = tools.get("memory_write")
        assert not spec.is_read_only

    def test_tools_have_capabilities(self):
        from edu_cloud.ai.registry import tools
        import edu_cloud.ai.tools.memory_tools  # noqa: F401

        read_spec = tools.get("memory_read")
        write_spec = tools.get("memory_write")
        assert ("system", "read") in read_spec.requires_capabilities
        assert ("system", "write") in write_spec.requires_capabilities


class TestToolAccessIntegration:
    def test_subject_teacher_can_read_memory(self):
        from edu_cloud.ai.tool_access import ToolAccessResolver
        from edu_cloud.ai.registry import tools
        import edu_cloud.ai.tools.memory_tools  # noqa: F401

        resolver = ToolAccessResolver()
        spec = tools.get("memory_read")
        caps = {("system", "read"): True}
        allowed = resolver._check_capabilities(spec.requires_capabilities, caps)
        assert allowed

    def test_subject_teacher_denied_write_when_explicit_false(self):
        """Capability model uses deny-only: explicit False blocks, missing key allows."""
        from edu_cloud.ai.tool_access import ToolAccessResolver
        from edu_cloud.ai.registry import tools
        import edu_cloud.ai.tools.memory_tools  # noqa: F401

        resolver = ToolAccessResolver()
        spec = tools.get("memory_write")
        # Explicit deny on system.write
        caps = {("system", "read"): True, ("system", "write"): False}
        allowed = resolver._check_capabilities(spec.requires_capabilities, caps)
        assert not allowed


class TestDefaultCapabilitiesIntegration:
    def test_init_creates_system_read_for_teachers(self):
        from edu_cloud.services.capability_service import DEFAULT_CAPABILITIES

        for role in ("subject_teacher", "homeroom_teacher", "grade_leader"):
            caps = DEFAULT_CAPABILITIES.get(role, {})
            assert "system" in caps, f"{role} missing 'system' domain in DEFAULT_CAPABILITIES"
            assert caps["system"].get("read") is True, f"{role} missing system.read"
            assert caps["system"].get("write") is False, f"{role} should have system.write=False"
