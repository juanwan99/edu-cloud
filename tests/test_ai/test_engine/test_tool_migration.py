"""Tests for tool migration pattern — verifies edu_tool decorator + Pydantic AI integration."""
from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from pydantic_ai import Agent, RunContext

from edu_cloud.ai.data_scope import DataScope
from edu_cloud.ai.engine.agent_deps import AgentDeps
from edu_cloud.ai.engine.budget import AgentBudget
from edu_cloud.ai.engine.tool_meta import EduToolMeta
from edu_cloud.ai.engine.tool_wrapper import edu_tool, get_all_tool_metas, TOOL_META_REGISTRY


# ── edu_tool decorator tests ──


def test_edu_tool_registers_meta():
    initial_count = len(TOOL_META_REGISTRY)

    @edu_tool(name="test_decorated_tool", module_code="test", domain="test", sensitivity="school")
    async def test_decorated_tool(ctx: RunContext[AgentDeps]) -> str:
        return "ok"

    assert "test_decorated_tool" in TOOL_META_REGISTRY
    meta = TOOL_META_REGISTRY["test_decorated_tool"]
    assert meta.module_code == "test"
    assert meta.is_read_only is True
    assert meta.risk_level == "low"

    # Cleanup
    del TOOL_META_REGISTRY["test_decorated_tool"]


def test_edu_tool_preserves_function_name():
    @edu_tool(name="named_tool", module_code="test")
    async def my_function(ctx: RunContext[AgentDeps]) -> str:
        """My docstring."""
        return "ok"

    assert my_function.__name__ == "my_function"
    assert my_function.__doc__ == "My docstring."

    del TOOL_META_REGISTRY["named_tool"]


def test_edu_tool_stores_meta_on_function():
    @edu_tool(name="meta_tool", module_code="test", sensitivity="pii", risk_level="high")
    async def tool_with_meta(ctx: RunContext[AgentDeps]) -> str:
        return "ok"

    assert hasattr(tool_with_meta, "_edu_meta")
    assert tool_with_meta._edu_meta.sensitivity == "pii"
    assert tool_with_meta._edu_meta.risk_level == "high"

    del TOOL_META_REGISTRY["meta_tool"]


def test_get_all_tool_metas():
    @edu_tool(name="meta_a", module_code="test")
    async def tool_a(ctx: RunContext[AgentDeps]) -> str:
        return "a"

    @edu_tool(name="meta_b", module_code="test")
    async def tool_b(ctx: RunContext[AgentDeps]) -> str:
        return "b"

    metas = get_all_tool_metas()
    assert "meta_a" in metas
    assert "meta_b" in metas

    del TOOL_META_REGISTRY["meta_a"]
    del TOOL_META_REGISTRY["meta_b"]


# ── Migrated students tools import test ──


def test_students_tools_register_meta():
    from edu_cloud.ai.engine.tools.students import ALL_TOOLS

    assert len(ALL_TOOLS) == 4

    names = {t.__name__ for t in ALL_TOOLS}
    assert "get_class_list" in names
    assert "get_class_roster" in names
    assert "search_students" in names
    assert "get_student_profile" in names

    for tool_func in ALL_TOOLS:
        assert hasattr(tool_func, "_edu_meta")
        meta = tool_func._edu_meta
        assert isinstance(meta, EduToolMeta)
        assert meta.is_read_only is True
        assert "subject_teacher" in meta.allowed_roles


def test_students_tool_metas_in_global_registry():
    from edu_cloud.ai.engine.tools import students  # noqa: F401

    metas = get_all_tool_metas()
    assert "get_class_list" in metas
    assert "get_class_roster" in metas
    assert metas["get_class_roster"].sensitivity == "student"
