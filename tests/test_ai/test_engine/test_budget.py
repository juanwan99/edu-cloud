"""Tests for AgentBudget — hard limits on resource consumption."""
from __future__ import annotations

import pytest

from edu_cloud.ai.engine.budget import AgentBudget, BudgetExhausted


def test_fresh_budget_allows_calls():
    b = AgentBudget(max_tool_calls=5, max_write_ops=2, max_tokens=1000)
    b.check_tool_call()
    b.check_tool_call(is_write=True)


def test_tool_call_limit():
    b = AgentBudget(max_tool_calls=2)
    b.debit_tool_call()
    b.debit_tool_call()
    with pytest.raises(BudgetExhausted, match="tool_calls"):
        b.check_tool_call()


def test_write_op_limit():
    b = AgentBudget(max_write_ops=1, max_tool_calls=100)
    b.debit_tool_call(is_write=True)
    with pytest.raises(BudgetExhausted, match="write_ops"):
        b.check_tool_call(is_write=True)


def test_read_allowed_after_write_exhausted():
    b = AgentBudget(max_write_ops=1, max_tool_calls=100)
    b.debit_tool_call(is_write=True)
    b.check_tool_call(is_write=False)


def test_token_limit():
    b = AgentBudget(max_tokens=100)
    b.debit_tokens(80)
    with pytest.raises(BudgetExhausted, match="tokens"):
        b.debit_tokens(30)


def test_wall_clock_limit():
    b = AgentBudget(max_wall_clock_seconds=0.0)
    with pytest.raises(BudgetExhausted, match="wall_clock"):
        b.check_tool_call()


def test_snapshot():
    b = AgentBudget(max_tokens=1000, max_tool_calls=10, max_write_ops=3)
    b.debit_tool_call()
    b.debit_tool_call(is_write=True)
    b.debit_tokens(250)
    snap = b.snapshot()
    assert snap["tokens"] == "250/1000"
    assert snap["tool_calls"] == "2/10"
    assert snap["write_ops"] == "1/3"
    assert "elapsed_s" in snap


def test_budget_exhausted_attributes():
    exc = BudgetExhausted("tokens", 100, 150)
    assert exc.dimension == "tokens"
    assert exc.limit == 100
    assert exc.current == 150
