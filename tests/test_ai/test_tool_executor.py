import asyncio
import pytest
from edu_cloud.ai.tool_executor import ToolExecutor, ToolOrchestrator, ToolBatch
from edu_cloud.ai.registry import ToolRegistry, ToolSpec
from edu_cloud.ai.tool_access import ToolAccessResolver
from edu_cloud.ai.tool_context import ToolContext, ToolResult
from edu_cloud.ai.schemas import ToolCall


# -- Helpers --

def _setup_registry():
    reg = ToolRegistry()

    @reg.register(name="read_a", description="Read A", is_read_only=True, sensitivity="school")
    async def read_a(input: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data={"from": "a"})

    @reg.register(name="read_b", description="Read B", is_read_only=True, sensitivity="school")
    async def read_b(input: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data={"from": "b"})

    @reg.register(name="write_c", description="Write C", is_read_only=False, sensitivity="school", risk_level="medium")
    async def write_c(input: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data={"written": True}, is_read_only=False)

    return reg


def _make_ctx():
    return ToolContext(db=None, school_id="S1", user_id="U1", role="admin")


# -- ToolOrchestrator tests --

def test_partition_all_reads():
    reg = _setup_registry()
    orch = ToolOrchestrator(reg)
    calls = [
        ToolCall(id="1", name="read_a", arguments={}, _raw={}),
        ToolCall(id="2", name="read_b", arguments={}, _raw={}),
    ]
    batches = orch.partition(calls)
    assert len(batches) == 1
    assert batches[0].concurrent is True
    assert len(batches[0].calls) == 2


def test_partition_mixed():
    reg = _setup_registry()
    orch = ToolOrchestrator(reg)
    calls = [
        ToolCall(id="1", name="read_a", arguments={}, _raw={}),
        ToolCall(id="2", name="write_c", arguments={}, _raw={}),
        ToolCall(id="3", name="read_b", arguments={}, _raw={}),
    ]
    batches = orch.partition(calls)
    assert len(batches) == 3
    assert batches[0].concurrent is True   # read_a
    assert batches[1].concurrent is False  # write_c
    assert batches[2].concurrent is True   # read_b


def test_partition_empty():
    reg = _setup_registry()
    orch = ToolOrchestrator(reg)
    batches = orch.partition([])
    assert batches == []


@pytest.mark.asyncio
async def test_orchestrator_execute():
    reg = _setup_registry()
    orch = ToolOrchestrator(reg)
    calls = [
        ToolCall(id="1", name="read_a", arguments={}, _raw={}),
        ToolCall(id="2", name="read_b", arguments={}, _raw={}),
    ]
    ctx = _make_ctx()
    batches = orch.partition(calls)
    results = await orch.execute(batches, ctx)
    assert len(results) == 2
    assert all(r.success for r in results)


@pytest.mark.asyncio
async def test_orchestrator_execute_empty():
    reg = _setup_registry()
    orch = ToolOrchestrator(reg)
    results = await orch.execute([], _make_ctx())
    assert results == []


# -- ToolExecutor tests --

@pytest.mark.asyncio
async def test_executor_run_one():
    reg = _setup_registry()
    executor = ToolExecutor(reg)
    ctx = _make_ctx()
    call = ToolCall(id="1", name="read_a", arguments={}, _raw={})
    result = await executor.run_one(call, ctx)
    assert result.success is True
    assert result.data == {"from": "a"}
    assert result.metadata["duration_ms"] >= 0


@pytest.mark.asyncio
async def test_executor_unknown_tool():
    reg = _setup_registry()
    executor = ToolExecutor(reg)
    ctx = _make_ctx()
    call = ToolCall(id="1", name="nonexistent", arguments={}, _raw={})
    result = await executor.run_one(call, ctx)
    assert result.success is False
    assert "Unknown tool" in result.error


@pytest.mark.asyncio
async def test_executor_handles_exception():
    reg = ToolRegistry()

    @reg.register(name="boom", description="Explodes", is_read_only=True, sensitivity="school")
    async def boom(input: dict, ctx: ToolContext) -> ToolResult:
        raise ValueError("kaboom")

    executor = ToolExecutor(reg)
    ctx = _make_ctx()
    call = ToolCall(id="1", name="boom", arguments={}, _raw={})
    result = await executor.run_one(call, ctx)
    assert result.success is False
    assert "kaboom" in result.error
    assert result.metadata["duration_ms"] >= 0
