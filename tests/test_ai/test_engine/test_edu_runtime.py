"""Tests for EduAgentRuntime — Pydantic AI agent orchestration."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from edu_cloud.ai.data_scope import DataScope
from edu_cloud.ai.engine.budget import AgentBudget
from edu_cloud.ai.engine.edu_runtime import EduAgentRuntime
from edu_cloud.ai.engine.tool_meta import EduToolMeta


def _scope() -> DataScope:
    return DataScope(
        user_id="u1", school_id="s1", role="subject_teacher",
        visible_class_ids=["c1"], visible_subject_codes=["math"],
        visible_grade_ids=None, visible_student_ids=None, district_ids=None,
        can_write=True, can_see_rankings=True, can_cross_school=False,
        persona="teacher_assistant", version=1, computed_at=datetime.now(),
    )


def _mock_memory():
    m = MagicMock()
    m.get_entity_memory = AsyncMock(return_value=None)
    return m


def _mock_anonymizer():
    m = MagicMock()
    m.anonymize_text = MagicMock(side_effect=lambda x: f"[ANON:{x}]")
    return m


def _mock_sessionmaker():
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    maker = MagicMock(return_value=session)
    return maker


def _runtime(**kwargs) -> EduAgentRuntime:
    defaults = dict(
        db_sessionmaker=_mock_sessionmaker(),
        user_id="u1",
        school_id="s1",
        role="subject_teacher",
        data_scope=_scope(),
        enabled_modules=frozenset({"exam"}),
        capabilities={},
        anonymizer=_mock_anonymizer(),
        memory=_mock_memory(),
        system_prompt="You are a helpful teacher assistant.",
    )
    defaults.update(kwargs)
    return EduAgentRuntime(**defaults)


def test_runtime_constructs_deps():
    rt = _runtime()
    deps = rt.deps
    assert deps.run_id
    assert deps.school_id == "s1"
    assert deps.role == "subject_teacher"
    assert deps.model_slot == "ai-chat"


def test_runtime_builds_agent():
    rt = _runtime()
    agent = rt.build_agent()
    assert agent is not None
    assert rt.agent is agent


def test_runtime_agent_has_correct_model():
    rt = _runtime(model_slot="agent-reasoning")
    assert rt.deps.model_slot == "agent-reasoning"


def test_runtime_budget_defaults():
    rt = _runtime()
    budget = rt.deps.budget
    assert budget.max_tokens == 100_000
    assert budget.max_tool_calls == 50
    assert budget.max_write_ops == 10


def test_runtime_custom_budget():
    b = AgentBudget(max_tokens=5000, max_tool_calls=10)
    rt = _runtime(budget=b)
    assert rt.deps.budget.max_tokens == 5000
    assert rt.deps.budget.max_tool_calls == 10


def test_runtime_policy_reflects_role():
    rt = _runtime(role="principal")
    assert rt.deps.policy._role == "principal"


def test_runtime_tool_meta_registry():
    meta = EduToolMeta(
        name="get_scores", module_code="exam", domain="analytics",
        risk_level="low", is_read_only=True,
        allowed_roles=frozenset({"subject_teacher"}),
        requires_capabilities=frozenset(), sensitivity="student",
    )
    rt = _runtime(tool_meta_registry={"get_scores": meta})
    assert rt.deps.policy.get_meta("get_scores") is meta


def test_runtime_trace_has_correct_ids():
    rt = _runtime(session_id="test-session-123")
    assert rt.deps.trace.session_id == "test-session-123"
    assert rt.deps.trace.run_id == rt.deps.run_id
