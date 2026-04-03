import asyncio
import pytest
from edu_cloud.ai.tool_executor import ToolExecutor, ToolOrchestrator, ToolBatch, MAX_TOOL_CONCURRENCY
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


def _make_ctx(db=None):
    return ToolContext(db=db, school_id="S1", user_id="U1", role="admin")


# -- ToolOrchestrator partition tests --

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
    assert batches[0].calls[0].name == "read_a"
    assert batches[0].calls[1].name == "read_b"


def test_partition_mixed():
    """F004: assert batch contents, not just boolean flags."""
    reg = _setup_registry()
    orch = ToolOrchestrator(reg)
    calls = [
        ToolCall(id="1", name="read_a", arguments={}, _raw={}),
        ToolCall(id="2", name="write_c", arguments={}, _raw={}),
        ToolCall(id="3", name="read_b", arguments={}, _raw={}),
    ]
    batches = orch.partition(calls)
    assert len(batches) == 3
    # Batch 0: read_a (concurrent)
    assert batches[0].concurrent is True
    assert [c.name for c in batches[0].calls] == ["read_a"]
    # Batch 1: write_c (serial)
    assert batches[1].concurrent is False
    assert [c.name for c in batches[1].calls] == ["write_c"]
    # Batch 2: read_b (concurrent)
    assert batches[2].concurrent is True
    assert [c.name for c in batches[2].calls] == ["read_b"]


def test_partition_all_writes():
    """F004: all write tools → each in its own serial batch."""
    reg = _setup_registry()
    orch = ToolOrchestrator(reg)
    calls = [
        ToolCall(id="1", name="write_c", arguments={}, _raw={}),
        ToolCall(id="2", name="write_c", arguments={}, _raw={}),
    ]
    batches = orch.partition(calls)
    assert len(batches) == 2
    assert all(not b.concurrent for b in batches)


def test_partition_empty():
    reg = _setup_registry()
    orch = ToolOrchestrator(reg)
    batches = orch.partition([])
    assert batches == []


def test_partition_unknown_tool_treated_as_read():
    """Unknown tools default to is_read_only=True."""
    reg = _setup_registry()
    orch = ToolOrchestrator(reg)
    calls = [
        ToolCall(id="1", name="unknown", arguments={}, _raw={}),
        ToolCall(id="2", name="read_a", arguments={}, _raw={}),
    ]
    batches = orch.partition(calls)
    assert len(batches) == 1
    assert batches[0].concurrent is True
    assert len(batches[0].calls) == 2


# -- ToolOrchestrator execute tests --

@pytest.mark.asyncio
async def test_orchestrator_execute():
    reg = _setup_registry()
    orch = ToolOrchestrator(reg)
    calls = [
        ToolCall(id="1", name="read_a", arguments={}, _raw={}),
        ToolCall(id="2", name="read_b", arguments={}, _raw={}),
    ]
    ctx = _make_ctx()  # db=None → concurrent allowed
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


@pytest.mark.asyncio
async def test_orchestrator_concurrent_when_no_db():
    """F003: verify concurrency actually happens when db=None (using timing)."""
    reg = ToolRegistry()
    started = []

    @reg.register(name="slow_a", description="Slow A", is_read_only=True, sensitivity="school")
    async def slow_a(input: dict, ctx: ToolContext) -> ToolResult:
        started.append("a")
        await asyncio.sleep(0.05)
        return ToolResult(success=True, data={"from": "a"})

    @reg.register(name="slow_b", description="Slow B", is_read_only=True, sensitivity="school")
    async def slow_b(input: dict, ctx: ToolContext) -> ToolResult:
        started.append("b")
        await asyncio.sleep(0.05)
        return ToolResult(success=True, data={"from": "b"})

    orch = ToolOrchestrator(reg)
    calls = [
        ToolCall(id="1", name="slow_a", arguments={}, _raw={}),
        ToolCall(id="2", name="slow_b", arguments={}, _raw={}),
    ]
    ctx = _make_ctx(db=None)
    batches = orch.partition(calls)

    import time
    t0 = time.monotonic()
    results = await orch.execute(batches, ctx)
    elapsed = time.monotonic() - t0

    assert len(results) == 2
    assert all(r.success for r in results)
    # If concurrent: ~50ms. If serial: ~100ms. Allow margin.
    assert elapsed < 0.09, f"Expected concurrent execution (<90ms), got {elapsed*1000:.0f}ms"


@pytest.mark.asyncio
async def test_orchestrator_serial_when_db_present():
    """F001: with real db session, concurrent batch falls back to serial."""
    reg = ToolRegistry()

    @reg.register(name="read_x", description="Read X", is_read_only=True, sensitivity="school")
    async def read_x(input: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data={"x": 1})

    orch = ToolOrchestrator(reg)
    calls = [
        ToolCall(id="1", name="read_x", arguments={}, _raw={}),
        ToolCall(id="2", name="read_x", arguments={}, _raw={}),
    ]
    # db is not None → serial fallback
    ctx = _make_ctx(db="fake_session")
    batches = orch.partition(calls)
    results = await orch.execute(batches, ctx)
    assert len(results) == 2
    assert all(r.success for r in results)


@pytest.mark.asyncio
async def test_orchestrator_max_concurrency_truncation():
    """F004: >MAX_TOOL_CONCURRENCY reads only executes first MAX_TOOL_CONCURRENCY."""
    reg = ToolRegistry()
    executed = []

    for i in range(15):
        name = f"read_{i}"

        @reg.register(name=name, description=f"Read {i}", is_read_only=True, sensitivity="school")
        async def tool_fn(input: dict, ctx: ToolContext, _name=name) -> ToolResult:
            executed.append(_name)
            return ToolResult(success=True, data={"n": _name})

    orch = ToolOrchestrator(reg)
    calls = [ToolCall(id=str(i), name=f"read_{i}", arguments={}, _raw={}) for i in range(15)]
    ctx = _make_ctx()
    batches = orch.partition(calls)
    results = await orch.execute(batches, ctx)
    assert len(results) == MAX_TOOL_CONCURRENCY  # truncated to 10


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


@pytest.mark.asyncio
async def test_executor_legacy_tool_compatibility():
    """F002/INV-001: run_one works with legacy **kwargs tools via registry.execute()."""
    reg = ToolRegistry()

    @reg.register(name="legacy_add", description="Add", parameters={}, is_read_only=True, sensitivity="school")
    async def legacy_add(a: int, b: int, _db=None) -> dict:
        return {"sum": a + b}

    executor = ToolExecutor(reg)
    ctx = _make_ctx()
    call = ToolCall(id="1", name="legacy_add", arguments={"a": 3, "b": 5}, _raw={})
    result = await executor.run_one(call, ctx)
    assert result.success is True
    assert result.data == {"sum": 8}
    assert result.metadata["duration_ms"] >= 0
