<!-- pre-takeover: archived for history, not active spec -->
# Agent 韧性与验证增强 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 Agent 系统 4 个真实 bug（OutputValidator 空转、并发截断、浅层 merge、error_count 语义混乱），增强韧性（LLM 重试、工具超时），改进输出验证和配置管理。

**Architecture:** 10 个文件的增量修改，无新模块。P0 修 bug → P1 加韧性 → P2 改验证 → P3 提配置。每个 Task 独立可测试。

**Tech Stack:** Python 3.12, asyncio, httpx, SQLAlchemy 2.0 (async), pytest

**Design:** `docs/plans/2026-04-06-agent-resilience-design.md`

---

## Contract Pack

```yaml
contract_pack:
  invariants:
    - id: INV-001
      statement: "DataScope fail-closed 行为不变——unknown 角色触发 DataScopeBuildError"
      verification: existing_test
      test_ref: tests/test_ai/test_data_scope.py::test_build_scope_fail_closed_unknown_role
    - id: INV-002
      statement: "SSE tool_result 事件载荷形状为 {tool: str, result: any}，与前端契约一致"
      verification: existing_test
      test_ref: tests/test_ai/test_ai_api_v2.py::test_sse_event_backward_compat + tests/test_ai/test_agent_loop.py::test_tool_call_and_answer
    - id: INV-003
      statement: "SSE 事件类型集合不变: thinking/plan/task_update/tool_call/tool_result/answer/error/done"
      verification: existing_test
      test_ref: tests/test_ai/test_agent_loop.py::test_tool_call_and_answer
    - id: INV-004
      statement: "42 个工具的函数签名和 ToolSpec 注册参数不变"
      verification: existing_test
      test_ref: tests/test_ai/test_tools_registration.py::test_total_tool_count + test_get_all_specs_returns_toolspec

  counter_examples:
    - id: CE-001
      scenario: "OutputValidator 接线修复后只读 'result' key，如果未来 agent_loop 改为发 'data' key，validator 又空转"
      tests_that_still_pass: "test_grounded.py（只测 validator 内部逻辑，不测接线）"
      mitigation: "Task 1 新增 runtime 入口级测试，mock supervisor 发 tool_result 事件，断言 collected_tool_results 非空"
    - id: CE-002
      scenario: "deep_merge 递归但 facts 含循环引用→无限递归 stack overflow"
      tests_that_still_pass: "test_memory_store.py 所有测试（均用有限嵌套数据）"
      mitigation: "deep_merge 添加 depth 限制（与 _collect_numbers 同策略 depth>5 截断）；Task 3 补 5 层嵌套测试"
    - id: CE-003
      scenario: "loop detection 只按历史总次数计数不要求连续——合法分页查询被误跳过"
      tests_that_still_pass: "test_agent_loop.py canonicalize 测试（只测工具函数，不测循环行为）"
      mitigation: "Task 8 补行为级测试：成功调用→相同工具→不跳过（因为中间有成功打断连续性）"

  risk_modules:
    - module: src/edu_cloud/ai/agent_loop.py
      reason: "P0-4 重构 error_count 语义 + P2-3 新增循环检测，改变 agent 状态机核心控制流"
    - module: src/edu_cloud/ai/tool_executor.py
      reason: "P0-2 修改并发逻辑 + P1-2 新增超时包装，影响所有工具执行路径"
    - module: src/edu_cloud/ai/grounded.py
      reason: "P2-1 全面重写验证逻辑，改变所有数字验证的判定结果"
    - module: src/edu_cloud/ai/llm_adapter.py
      reason: "P1-1 新增重试层，影响所有 LLM 调用路径"
    - module: src/edu_cloud/ai/runtime.py
      reason: "P0-1 修改 OutputValidator 数据收集逻辑"

  test_debt:
  semantic_regression:
    required: true
    risk_tags:
      - state_machine        # P0-4 重构 error_count → dual streak counters
      - threshold_default     # P3-1 Tier 阈值外提, P2-3 循环检测阈值
      - selection_strategy    # P3-2 Router 关键词外提
    oracles:
      - id: ORC-001
        type: temporal_trace
        statement: "LLM 连续 3 次异常后 agent 循环必须终止并 yield error 事件"
        protects: [state_machine]
        verification: pending_test
        note: "Task 4 新增 TestErrorStreakSemantics 覆盖"
      - id: ORC-002
        type: forbidden_strategy
        statement: "禁止单 turn 多工具部分失败就递增 tool_fail_streak — 只有全部失败才递增"
        protects: [state_machine]
        verification: pending_test
        note: "Task 4 新增测试覆盖"
      - id: ORC-003
        type: temporal_trace
        statement: "相同工具+相同参数+相同错误文本连续 2 次失败后第 3 次调用被跳过；中间插入成功则链断裂不跳过"
        protects: [state_machine, threshold_default]
        verification: pending_test
        note: "Task 8 TestLoopDetectionBehavior 覆盖"
      - id: ORC-004
        type: forbidden_strategy
        statement: "禁止历史总次数计数替代连续性检测 — 必须从 _recent_calls 末尾反向遍历且遇到非匹配即 break"
        protects: [state_machine]
        verification: pending_test
        note: "Task 8 test_success_breaks_chain 覆盖"
      - id: ORC-005
        type: temporal_trace
        statement: "自定义 Tier 阈值 [50K,10K] 时，60K context 模型被 determine_tier() 判定为 tier 1 而非 tier 2"
        protects: [threshold_default]
        verification: pending_test
        note: "Task 9 test_custom_t1_threshold_affects_determine_tier 覆盖"
      - id: ORC-006
        type: temporal_trace
        statement: "自定义关键词 ['自定义词'] 时，route() 对匹配消息返回 tier='advanced'，对不匹配返回 tier='standard'"
        protects: [selection_strategy]
        verification: pending_test
        note: "Task 10 test_custom_keywords_affects_route_decision 覆盖"

  test_debt:
    - item: "chat_stream() 路径未加重试"
      reason: "当前无调用点（GPT 确认），优先做 chat() 路径"
      deadline: "2026-04-20"
    - item: "工具超时后写工具的 rollback"
      reason: "当前写工具为 memory_write/generate_report 等，超时风险低；需要事务机制支持"
      deadline: "2026-04-30"
```

---

### Task 1: OutputValidator 接线修复

**Files:**
- Modify: `src/edu_cloud/ai/runtime.py:171-176`
- Test: `tests/test_ai/test_runtime.py` (新增测试)

- [ ] **Step 1: Write failing test — 旧代码下 OutputValidator 收集为空，新代码下非空**

```python
# tests/test_ai/test_runtime.py — 追加

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from edu_cloud.ai.runtime import AgentRuntime, AgentContext
from edu_cloud.ai.schemas import AgentEvent
from edu_cloud.ai.tool_context import ToolResult


class TestOutputValidatorWiring:
    """P0-1: OutputValidator must collect tool_result events via runtime entry."""

    @pytest.mark.asyncio
    async def test_validator_collects_from_result_key(self):
        """AgentRuntime.run() must feed tool_result['result'] to OutputValidator.

        Before fix: runtime looks for 'data' key — collected_tool_results is always empty.
        After fix: runtime reads 'result' key — validator gets actual tool data.
        """
        runtime = AgentRuntime()

        # Mock supervisor to yield a tool_result event with "result" key
        # (matching agent_loop.py:186 format)
        mock_events = [
            AgentEvent(type="tool_result", data={
                "tool": "get_exam_scores",
                "result": {"avg_score": 85.3},
            }),
            AgentEvent(type="answer", data={"content": "平均分 99 分"}),
            AgentEvent(type="done", data={"turns": 1, "tokens": 100, "channel": "primary"}),
        ]

        # Patch validator to capture what it receives
        captured_results = []
        original_validate = runtime._validator.validate
        def spy_validate(response, tool_results):
            captured_results.extend(tool_results)
            return original_validate(response, tool_results)
        runtime._validator.validate = spy_validate

        # Patch internals to skip real LLM/DB calls
        with patch.object(runtime, '_model_router') as mr, \
             patch.object(runtime, '_probe') as probe, \
             patch.object(runtime, '_memory_injector') as mi, \
             patch.object(runtime, '_tool_resolver') as tr:
            mr.route.return_value = MagicMock(tier="standard")
            probe.determine_tier = AsyncMock(return_value=3)
            mi.build_context = AsyncMock(return_value="")
            tr.resolve.return_value = []

            # Patch Supervisor to yield our mock events
            with patch('edu_cloud.ai.runtime.Supervisor') as MockSupervisor:
                mock_sup = MagicMock()
                async def mock_handle(**kwargs):
                    for e in mock_events:
                        yield e
                mock_sup.handle = mock_handle
                mock_sup.model_tier = "tier3"
                mock_sup.get_history.return_value = []
                MockSupervisor.return_value = mock_sup

                # Patch LLMProxyAdapter.close
                with patch('edu_cloud.ai.runtime.LLMProxyAdapter') as MockAdapter:
                    mock_adapter = AsyncMock()
                    mock_adapter.context_window_size.return_value = 128000
                    MockAdapter.return_value = mock_adapter

                    ctx = AgentContext(
                        db=MagicMock(), user_id="u1", school_id="s1",
                        role="admin", data_scope=None, session_id="sess1",
                    )

                    events = []
                    async for event in runtime.run("test", ctx):
                        events.append(event)

        # KEY ASSERTION: validator received tool data (non-empty)
        assert len(captured_results) > 0, \
            "OutputValidator received no tool results — wiring bug still present"
        assert captured_results[0].data["avg_score"] == 85.3
```

- [ ] **Step 2: Run test to verify it fails with OLD code**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_runtime.py::TestOutputValidatorWiring::test_validator_collects_from_result_key -v`
Expected: FAIL — `AssertionError: OutputValidator received no tool results` (old code reads "data" key, misses "result")

- [ ] **Step 3: Apply fix to runtime.py**

Replace `runtime.py:171-176`:

```python
                # F001: collect tool_result data for OutputValidator
                if event.type == "tool_result" and isinstance(event.data, dict):
                    payload = event.data.get("result", event.data.get("data"))
                    if payload is not None and not (
                        isinstance(payload, dict) and "error" in payload
                    ):
                        collected_tool_results.append(
                            ToolResult(success=True, data=payload)
                        )
```

- [ ] **Step 4: Run full test suite to confirm no regression**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_runtime.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/ai/runtime.py tests/test_ai/test_runtime.py
git commit -m "fix(ai): OutputValidator 接线修复 — 读 'result' key 而非 'data'"
```

**审查清单:**
- ✓ runtime.py:173 从查找 `"data"` 改为 `get("result", get("data"))` 兼容读取
- ✓ 过滤 error payload（含 "error" key 的 dict 不收集）
- ✗ 反向: 如果保留旧代码（查 "data"），collected_tool_results 始终为空

**边界条件:**
- event.data 为 None → `isinstance(None, dict)` 为 False，跳过
- event.data["result"] 为非 dict 数据（如 list）→ error 检查不触发，正常收集
- event.data 同时有 "result" 和 "data" key → 优先用 "result"

**测试契约:**
1. tool_result 事件中 "result" key 被正确收集
   - 入口: AgentRuntime.run() 的事件流
   - 反例: 旧代码查 "data" key 会导致 collected_tool_results 始终为空
   - 边界: error payload / None payload / fallback "data" key
   - 回归: 防止 OutputValidator 再次空转
   - 命令: `pytest tests/test_ai/test_runtime.py::TestOutputValidatorWiring -v`

---

### Task 2: 并发批次截断修复

**Files:**
- Modify: `src/edu_cloud/ai/tool_executor.py:99-103`
- Test: `tests/test_ai/test_tool_executor.py` (追加测试)

- [ ] **Step 1: Write failing test — >10 个并发工具不应丢弃**

```python
# tests/test_ai/test_tool_executor.py — 追加

import asyncio
import pytest
from edu_cloud.ai.tool_executor import ToolOrchestrator, ToolBatch, MAX_TOOL_CONCURRENCY
from edu_cloud.ai.registry import ToolRegistry
from edu_cloud.ai.tool_context import ToolContext, ToolResult
from edu_cloud.ai.schemas import ToolCall


class TestBatchTruncationFix:
    """P0-2: concurrent batches > MAX_TOOL_CONCURRENCY must not drop calls."""

    @pytest.mark.asyncio
    async def test_all_concurrent_calls_executed(self):
        """12 concurrent read tools must all return results."""
        reg = ToolRegistry()
        call_count = 0

        for i in range(12):
            name = f"read_{i}"

            @reg.register(name=name, description=f"Read {i}", is_read_only=True, sensitivity="school")
            async def handler(input: dict, ctx: ToolContext, _n=name) -> ToolResult:
                nonlocal call_count
                call_count += 1
                return ToolResult(success=True, data={"tool": _n})

        orch = ToolOrchestrator(reg)
        calls = [ToolCall(id=str(i), name=f"read_{i}", arguments={}, _raw={}) for i in range(12)]
        batches = orch.partition(calls)

        ctx = ToolContext(db=None, school_id="S1", user_id="U1", role="admin")
        results = await orch.execute(batches, ctx)

        assert len(results) == 12, f"Expected 12 results, got {len(results)}"
        assert call_count == 12
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_exactly_max_concurrent(self):
        """Exactly MAX_TOOL_CONCURRENCY calls should still work."""
        reg = ToolRegistry()

        for i in range(MAX_TOOL_CONCURRENCY):
            @reg.register(name=f"read_{i}", description=f"R{i}", is_read_only=True, sensitivity="school")
            async def handler(input: dict, ctx: ToolContext, _n=i) -> ToolResult:
                return ToolResult(success=True, data={"n": _n})

        orch = ToolOrchestrator(reg)
        calls = [ToolCall(id=str(i), name=f"read_{i}", arguments={}, _raw={}) for i in range(MAX_TOOL_CONCURRENCY)]
        batches = orch.partition(calls)

        ctx = ToolContext(db=None, school_id="S1", user_id="U1", role="admin")
        results = await orch.execute(batches, ctx)

        assert len(results) == MAX_TOOL_CONCURRENCY
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_tool_executor.py::TestBatchTruncationFix::test_all_concurrent_calls_executed -v`
Expected: FAIL — only 10 results returned instead of 12

- [ ] **Step 3: Apply fix to tool_executor.py**

Replace `tool_executor.py:99-103`:

```python
            if batch.concurrent and can_concurrent and len(batch.calls) > 1:
                for i in range(0, len(batch.calls), MAX_TOOL_CONCURRENCY):
                    chunk = batch.calls[i:i + MAX_TOOL_CONCURRENCY]
                    chunk_results = await asyncio.gather(
                        *[self._executor.run_one(call, ctx) for call in chunk]
                    )
                    results.extend(chunk_results)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_tool_executor.py::TestBatchTruncationFix -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/ai/tool_executor.py tests/test_ai/test_tool_executor.py
git commit -m "fix(ai): 并发批次截断修复 — 分片循环处理 >MAX_TOOL_CONCURRENCY 调用"
```

**审查清单:**
- ✓ 12 个并发工具调用全部返回结果
- ✓ MAX_TOOL_CONCURRENCY 个调用正常工作（边界）
- ✗ 反向: 旧代码 `batch.calls[:MAX]` 静默丢弃第 11 个以后的调用

**边界条件:**
- 恰好 MAX_TOOL_CONCURRENCY 个 → 单批次执行，不触发分片
- MAX_TOOL_CONCURRENCY + 1 个 → 两批次（10+1）
- 0 个 → 空列表，range(0,0,10) 不执行

---

### Task 3: 深层 merge

**Files:**
- Modify: `src/edu_cloud/ai/memory_store.py:1-5, 38-40, 184-186`
- Test: `tests/test_ai/test_memory_store.py` (追加测试)

- [ ] **Step 1: Write failing test — 嵌套 dict 合并应保留已有字段**

```python
# tests/test_ai/test_memory_store.py — 追加

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


class TestDeepMerge:
    """P0-3: nested dict merge must preserve existing nested fields."""

    @pytest.mark.asyncio
    async def test_nested_dict_preserved(self, db_engine, store):
        """Updating nested dict should deep-merge, not overwrite."""
        async with AsyncSession(db_engine) as db:
            await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-dm", facts={"scores": {"math": 90, "english": 85}},
            )
            result = await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-dm", facts={"scores": {"math": 95}},
            )
            # math updated, english preserved
            assert result.facts["scores"]["math"] == 95
            assert result.facts["scores"]["english"] == 85

    @pytest.mark.asyncio
    async def test_deep_merge_three_levels(self, db_engine, store):
        """Three-level nesting should be recursively merged."""
        async with AsyncSession(db_engine) as db:
            await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-3l", facts={"profile": {"scores": {"math": 90}}},
            )
            result = await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-3l", facts={"profile": {"scores": {"english": 85}}},
            )
            assert result.facts["profile"]["scores"]["math"] == 90
            assert result.facts["profile"]["scores"]["english"] == 85

    @pytest.mark.asyncio
    async def test_scalar_overwrite(self, db_engine, store):
        """Non-dict values should still overwrite."""
        async with AsyncSession(db_engine) as db:
            await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-so", facts={"name": "张三", "grade": 3},
            )
            result = await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-so", facts={"grade": 4},
            )
            assert result.facts["name"] == "张三"
            assert result.facts["grade"] == 4

    @pytest.mark.asyncio
    async def test_list_replaces_not_merges(self, db_engine, store):
        """Lists should be replaced entirely, not merged."""
        async with AsyncSession(db_engine) as db:
            await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-lr", facts={"tags": ["a", "b"]},
            )
            result = await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-lr", facts={"tags": ["c"]},
            )
            assert result.facts["tags"] == ["c"]

    @pytest.mark.asyncio
    async def test_none_value_overwrites(self, db_engine, store):
        """None update value should overwrite existing."""
        async with AsyncSession(db_engine) as db:
            await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-nv", facts={"note": "old"},
            )
            result = await store.upsert_entity(
                db, school_id="sch-1", entity_type="student",
                entity_id="stu-nv", facts={"note": None},
            )
            assert result.facts["note"] is None
```

- [ ] **Step 2: Run test to verify nested merge fails**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_memory_store.py::TestDeepMerge::test_nested_dict_preserved -v`
Expected: FAIL — `KeyError: 'english'` because shallow merge overwrites entire "scores" dict

- [ ] **Step 3: Implement _deep_merge and apply to memory_store.py**

Add function at top of `memory_store.py` (after imports, before class):

```python
def _deep_merge(base: dict, update: dict) -> dict:
    """Recursively merge update into base. Returns new dict (no mutation).

    - dict + dict → recursive merge
    - anything else → update wins
    """
    result = {**base}
    for k, v in update.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result
```

Replace `memory_store.py:39` (`merged = {**existing.facts, **facts}`):
```python
            merged = _deep_merge(existing.facts, facts)
```

Replace `memory_store.py:185` (`merged = {**proj.state, **state_updates}`):
```python
            merged = _deep_merge(proj.state, state_updates)
```

- [ ] **Step 4: Run all deep merge tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_memory_store.py::TestDeepMerge -v`
Expected: All PASS

- [ ] **Step 5: Run existing memory_store tests for regression**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_memory_store.py -v`
Expected: All PASS (existing shallow-merge tests still pass because top-level merge behavior unchanged)

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/ai/memory_store.py tests/test_ai/test_memory_store.py
git commit -m "fix(ai): 深层 merge 修复 — 嵌套 dict 递归合并不丢字段"
```

**审查清单:**
- ✓ 嵌套 dict 递归合并，保留已有字段
- ✓ 顶层标量/list 仍覆盖（向后兼容）
- ✓ _deep_merge 返回新 dict，不原地修改
- ✗ 反向: 旧浅层 merge 会丢失嵌套字段

**边界条件:**
- 空 base dict `{}` + 任意 update → 等于 update
- None value 覆盖已有值 → 覆盖成功
- 三层嵌套 → 递归正确

---

### Task 4: error_count 语义重构

**Files:**
- Modify: `src/edu_cloud/ai/agent_loop.py:30-35, 136-142, 190, 193, 212-214`
- Test: `tests/test_ai/test_agent_loop.py` (追加测试)

- [ ] **Step 1: Write failing tests — 双计数器语义**

```python
# tests/test_ai/test_agent_loop.py — 追加

from edu_cloud.ai.agent_loop import AgentState


class TestErrorStreakSemantics:
    """P0-4: dual error streak counters with per-turn semantics."""

    def test_agent_state_has_dual_counters(self):
        """AgentState should have llm_error_streak and tool_fail_streak."""
        state = AgentState(messages=[])
        assert hasattr(state, "llm_error_streak")
        assert hasattr(state, "tool_fail_streak")
        assert state.llm_error_streak == 0
        assert state.tool_fail_streak == 0

    def test_no_legacy_error_count(self):
        """Legacy error_count should not exist."""
        state = AgentState(messages=[])
        assert not hasattr(state, "error_count")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_agent_loop.py::TestErrorStreakSemantics -v`
Expected: FAIL — `error_count` exists, `llm_error_streak` doesn't

- [ ] **Step 3: Refactor AgentState**

In `agent_loop.py:30-35`, replace:

```python
@dataclass
class AgentState:
    messages: list[Message]
    turn_count: int = 0
    token_count: int = 0
    llm_error_streak: int = 0
    tool_fail_streak: int = 0
    channel: str = "primary"
```

- [ ] **Step 4: Update LLM error handling (agent_loop.py:136-142)**

Replace the except block:

```python
                except Exception as exc:
                    state.llm_error_streak += 1
                    logger.error("LLM call failed (streak %d): %s", state.llm_error_streak, exc)
                    if state.llm_error_streak >= 3:
                        yield AgentEvent(type="error", data={"message": f"LLM 调用失败: {exc}"})
                        break
                    continue
```

- [ ] **Step 5: Update tool execution success/fail (agent_loop.py:190)**

Replace `state.error_count = 0` with per-turn tool streak logic:

```python
                    # P0-4: per-turn tool fail streak
                    all_failed = all(not r.success for r in results)
                    any_succeeded = any(r.success for r in results)
                    if all_failed:
                        state.tool_fail_streak += 1
                        logger.warning("All tools failed this turn (streak %d)", state.tool_fail_streak)
                        if state.tool_fail_streak >= 3:
                            yield AgentEvent(type="error", data={
                                "message": "工具连续失败，停止执行",
                            })
                            break
                    elif any_succeeded:
                        state.tool_fail_streak = 0

                    # Reset LLM streak on successful LLM response (tool branch = LLM succeeded)
                    state.llm_error_streak = 0
                    continue
```

- [ ] **Step 6: Update direct answer path (agent_loop.py:193+)**

After `if resp.stop_reason == "end_turn" and resp.content:`, add LLM streak reset:

```python
                if resp.stop_reason == "end_turn" and resp.content:
                    state.llm_error_streak = 0  # P0-4: successful LLM response
                    state.messages.append(Message(role="assistant", content=resp.content))
```

- [ ] **Step 7: Update outer loop break condition (agent_loop.py:212-214)**

Replace `if state.error_count >= 3:` with:

```python
            if state.llm_error_streak >= 3 or state.tool_fail_streak >= 3:
                break
```

- [ ] **Step 8: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_agent_loop.py -v`
Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add src/edu_cloud/ai/agent_loop.py tests/test_ai/test_agent_loop.py
git commit -m "fix(ai): error_count 语义重构 — 拆为 llm_error_streak + tool_fail_streak"
```

**审查清单:**
- ✓ AgentState 有 llm_error_streak 和 tool_fail_streak，无旧 error_count
- ✓ LLM 异常递增 llm_error_streak，成功 LLM 响应（含直接回答）重置
- ✓ 某轮工具全部失败才递增 tool_fail_streak，有任一成功则重置
- ✗ 反向: 旧 error_count 只计 LLM 异常且在工具分支无条件重置

**边界条件:**
- 单轮发 3 个工具、2 成功 1 失败 → tool_fail_streak 不递增（非全部失败）
- LLM 连续 3 次异常 → 熔断
- 工具全部失败 → 递增；下一轮有一个成功 → 重置

**测试契约:**
1. 双计数器存在且旧字段移除
   - 入口: AgentState 构造
   - 反例: 旧代码 AgentState 有 error_count 无 llm_error_streak
   - 边界: 初始值均为 0
   - 回归: 防止旧语义回归
   - 命令: `pytest tests/test_ai/test_agent_loop.py::TestErrorStreakSemantics -v`

---

### Task 5: LLM 分级重试

**Files:**
- Modify: `src/edu_cloud/ai/llm_adapter.py:104-112`
- Test: `tests/test_ai/test_llm_adapter.py` (追加测试)

- [ ] **Step 1: Write failing tests — 分级重试策略**

```python
# tests/test_ai/test_llm_adapter.py — 追加

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMRequest
from edu_cloud.ai.schemas import Message


class TestLLMRetry:
    """P1-1: graded retry for LLM calls."""

    @pytest.mark.asyncio
    async def test_429_retries_up_to_3_times(self):
        """429 Too Many Requests should retry up to 3 times."""
        adapter = LLMProxyAdapter(base_url="http://fake:8100", slot="test")
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.status_code = 429
            resp.headers = {}
            resp.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError("429", request=MagicMock(), response=resp)
            )
            return resp

        adapter._http = AsyncMock()
        adapter._http.post = mock_post

        with pytest.raises(httpx.HTTPStatusError):
            await adapter.chat(LLMRequest(
                messages=[Message(role="user", content="test")],
            ))

        assert call_count == 4  # 1 initial + 3 retries

    @pytest.mark.asyncio
    async def test_500_retries_once(self):
        """500 should retry exactly once."""
        adapter = LLMProxyAdapter(base_url="http://fake:8100", slot="test")
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.status_code = 500
            resp.headers = {}
            resp.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError("500", request=MagicMock(), response=resp)
            )
            return resp

        adapter._http = AsyncMock()
        adapter._http.post = mock_post

        with pytest.raises(httpx.HTTPStatusError):
            await adapter.chat(LLMRequest(
                messages=[Message(role="user", content="test")],
            ))

        assert call_count == 2  # 1 initial + 1 retry

    @pytest.mark.asyncio
    async def test_400_no_retry(self):
        """400 Bad Request should not retry."""
        adapter = LLMProxyAdapter(base_url="http://fake:8100", slot="test")
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.status_code = 400
            resp.headers = {}
            resp.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError("400", request=MagicMock(), response=resp)
            )
            return resp

        adapter._http = AsyncMock()
        adapter._http.post = mock_post

        with pytest.raises(httpx.HTTPStatusError):
            await adapter.chat(LLMRequest(
                messages=[Message(role="user", content="test")],
            ))

        assert call_count == 1  # No retry
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_llm_adapter.py::TestLLMRetry -v`
Expected: FAIL — no retry logic, call_count always 1

- [ ] **Step 3: Implement retry in llm_adapter.py**

Add `_post_with_retry` method to `LLMProxyAdapter` (after `set_capabilities`):

```python
    async def _post_with_retry(self, url: str, headers: dict, json: dict) -> httpx.Response:
        """POST with graded retry. Uses config LLM_MAX_RETRIES / LLM_TIMEOUT."""
        import asyncio
        from edu_cloud.config import settings

        max_retries_429 = min(settings.LLM_MAX_RETRIES, 3)
        last_exc: Exception | None = None

        for attempt in range(1 + max_retries_429):  # 1 initial + retries
            try:
                resp = await self._http.post(url, headers=headers, json=json)
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                status = exc.response.status_code
                if status == 429:
                    if attempt < max_retries_429:
                        retry_after = float(exc.response.headers.get("Retry-After", 1 << attempt))
                        await asyncio.sleep(min(retry_after, 8))
                        continue
                elif 500 <= status <= 503:
                    if attempt == 0:
                        await asyncio.sleep(1)
                        continue
                raise  # 4xx (non-429) or exhausted retries
            except httpx.TimeoutException as exc:
                last_exc = exc
                if attempt == 0:
                    continue
                raise
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt == 0:
                    await asyncio.sleep(1)
                    continue
                raise

        raise last_exc  # type: ignore[misc]
```

Update `chat()` method to use `_post_with_retry`:

```python
    async def chat(self, request: LLMRequest) -> LLMResponse:
        payload = self._build_payload(request)
        resp = await self._post_with_retry(
            f"{self._base_url}/v1/chat/completions",
            headers={"X-LLM-Slot": self._slot},
            json=payload,
        )
        return self._parse_response(resp.json())
```

- [ ] **Step 4: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_llm_adapter.py::TestLLMRetry -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/ai/llm_adapter.py tests/test_ai/test_llm_adapter.py
git commit -m "feat(ai): LLM 分级重试 — 429 退避3次 / 5xx 重试1次 / 4xx 不重试"
```

**审查清单:**
- ✓ 429 指数退避重试 ≤3 次，尊重 Retry-After
- ✓ 500-503 重试 1 次
- ✓ 4xx（非 429）不重试
- ✓ 复用 config.py LLM_MAX_RETRIES
- ✗ 反向: 旧代码无重试，所有异常直接传播

**边界条件:**
- Retry-After header 值 > 8 → clamp 到 8 秒
- 429 后第二次成功 → 返回正常结果
- config LLM_MAX_RETRIES=0 → 不重试

---

### Task 6: 工具执行超时

**Files:**
- Modify: `src/edu_cloud/ai/tool_executor.py:34-54` (ToolExecutor.run_one)
- Test: `tests/test_ai/test_tool_executor.py` (追加测试)

- [ ] **Step 1: Write failing test — 慢工具应超时返回错误**

```python
# tests/test_ai/test_tool_executor.py — 追加

import asyncio
import pytest
from edu_cloud.ai.tool_executor import ToolExecutor, ToolOrchestrator, ToolBatch
from edu_cloud.ai.registry import ToolRegistry
from edu_cloud.ai.tool_context import ToolContext, ToolResult
from edu_cloud.ai.schemas import ToolCall


class TestToolTimeout:
    """P1-2: slow tools should timeout and return error ToolResult."""

    @pytest.mark.asyncio
    async def test_slow_read_tool_times_out(self):
        """Read-only tool exceeding 30s (simulated) returns failure."""
        reg = ToolRegistry()

        @reg.register(name="slow_read", description="Slow", is_read_only=True, sensitivity="school")
        async def slow_read(input: dict, ctx: ToolContext) -> ToolResult:
            await asyncio.sleep(100)  # way too slow
            return ToolResult(success=True, data={})

        orch = ToolOrchestrator(reg)
        ctx = ToolContext(db=None, school_id="S1", user_id="U1", role="admin")

        calls = [ToolCall(id="1", name="slow_read", arguments={}, _raw={})]
        batches = orch.partition(calls)

        # Use short timeout for test
        results = await orch.execute(batches, ctx, default_read_timeout=0.1)

        assert len(results) == 1
        assert results[0].success is False
        assert "超时" in results[0].error

    @pytest.mark.asyncio
    async def test_fast_tool_succeeds(self):
        """Normal-speed tool should succeed within timeout."""
        reg = ToolRegistry()

        @reg.register(name="fast_read", description="Fast", is_read_only=True, sensitivity="school")
        async def fast_read(input: dict, ctx: ToolContext) -> ToolResult:
            return ToolResult(success=True, data={"ok": True})

        orch = ToolOrchestrator(reg)
        ctx = ToolContext(db=None, school_id="S1", user_id="U1", role="admin")

        calls = [ToolCall(id="1", name="fast_read", arguments={}, _raw={})]
        batches = orch.partition(calls)
        results = await orch.execute(batches, ctx)

        assert len(results) == 1
        assert results[0].success is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_tool_executor.py::TestToolTimeout::test_slow_read_tool_times_out -v --timeout=5`
Expected: FAIL — test hangs (no timeout in current code) or times out at pytest level

- [ ] **Step 3: Implement timeout in ToolOrchestrator.execute**

Update `ToolOrchestrator.execute()` signature and body:

```python
    async def execute(
        self,
        batches: list[ToolBatch],
        ctx: ToolContext,
        *,
        default_read_timeout: float = 30.0,
        default_write_timeout: float = 60.0,
    ) -> list[ToolResult]:
        can_concurrent = ctx.db is None
        results: list[ToolResult] = []
        for batch in batches:
            if batch.concurrent and can_concurrent and len(batch.calls) > 1:
                for i in range(0, len(batch.calls), MAX_TOOL_CONCURRENCY):
                    chunk = batch.calls[i:i + MAX_TOOL_CONCURRENCY]
                    chunk_results = await asyncio.gather(
                        *[self._run_with_timeout(call, ctx, default_read_timeout, default_write_timeout)
                          for call in chunk]
                    )
                    results.extend(chunk_results)
            else:
                for call in batch.calls:
                    results.append(
                        await self._run_with_timeout(call, ctx, default_read_timeout, default_write_timeout)
                    )
        return results

    async def _run_with_timeout(
        self,
        call: ToolCall,
        ctx: ToolContext,
        read_timeout: float,
        write_timeout: float,
    ) -> ToolResult:
        spec = self._registry.get(call.name)
        timeout = read_timeout if (spec and spec.is_read_only) else write_timeout
        try:
            return await asyncio.wait_for(self._executor.run_one(call, ctx), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("Tool %s timed out after %.0fs", call.name, timeout)
            return ToolResult(success=False, error=f"工具执行超时({timeout:.0f}s)")
        except asyncio.CancelledError:
            return ToolResult(success=False, error="工具执行被取消")
```

- [ ] **Step 4: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_tool_executor.py::TestToolTimeout -v --timeout=10`
Expected: All PASS

- [ ] **Step 5: Run full tool_executor tests for regression**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_tool_executor.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/ai/tool_executor.py tests/test_ai/test_tool_executor.py
git commit -m "feat(ai): 工具执行超时 — 只读 30s / 写入 60s / CancelledError 安全捕获"
```

**审查清单:**
- ✓ 只读工具默认 30s 超时，写入工具 60s
- ✓ 超时返回 ToolResult(success=False)，不抛异常
- ✓ CancelledError 单独捕获（BaseException）
- ✗ 反向: 旧代码无超时，慢工具会阻塞整个 SSE 流

**边界条件:**
- 工具恰好在超时边缘完成 → 正常返回
- 未知工具（spec=None）→ 默认用 write_timeout（保守）
- 超时参数可通过 execute() 覆盖（测试用）

---

### Task 7: OutputValidator 结构化 + 百分数转换修复

**Files:**
- Modify: `src/edu_cloud/ai/grounded.py` (全面重构)
- Test: `tests/test_ai/test_grounded.py` (追加测试)

- [ ] **Step 1: Write failing tests — 分类型容差 + 百分数条件转换**

```python
# tests/test_ai/test_grounded.py — 追加

import pytest
from edu_cloud.ai.grounded import OutputValidator, NumberToken
from edu_cloud.ai.tool_context import ToolResult


class TestNumberToken:
    """P2-1: structured number extraction."""

    def test_extract_score_unit(self):
        v = OutputValidator()
        tokens = v._extract_number_tokens("平均分 85.3 分，最高 100 分")
        values = {t.value for t in tokens}
        assert 85.3 in values
        assert 100.0 in values
        assert all(t.unit == "分" for t in tokens)

    def test_extract_count_unit(self):
        v = OutputValidator()
        tokens = v._extract_number_tokens("共 42 人参加，3 班共 38 人")
        units = {t.unit for t in tokens}
        assert "人" in units

    def test_extract_percent_unit(self):
        v = OutputValidator()
        tokens = v._extract_number_tokens("及格率 85%")
        assert any(t.unit == "%" and t.value == 85.0 for t in tokens)


class TestTypedTolerance:
    """P2-1: type-specific validation tolerance."""

    def test_score_strict_tolerance(self):
        """Score 85.3 reported as 86 should be flagged (>0.5% error)."""
        v = OutputValidator()
        result = v.validate(
            "平均分 86 分",
            [ToolResult(success=True, data={"avg_score": 85.3})],
        )
        assert result.status == "fail"

    def test_score_within_tolerance(self):
        """Score 85.3 reported as 85.3 should pass."""
        v = OutputValidator()
        result = v.validate(
            "平均分 85.3 分",
            [ToolResult(success=True, data={"avg_score": 85.3})],
        )
        assert result.status == "pass"

    def test_count_must_be_exact(self):
        """Count must be exact — 42 reported as 43 is fail."""
        v = OutputValidator()
        result = v.validate(
            "共 43 人",
            [ToolResult(success=True, data={"student_count": 42})],
        )
        assert result.status == "fail"


class TestPercentConversion:
    """P2-2: conditional percent conversion."""

    def test_rate_field_converts(self):
        """Field named 'pass_rate' with value 0.85 should match '85%'."""
        v = OutputValidator()
        result = v.validate(
            "及格率 85%",
            [ToolResult(success=True, data={"pass_rate": 0.85})],
        )
        assert result.status == "pass"

    def test_non_rate_field_no_convert(self):
        """Field named 'coefficient' with value 0.85 should NOT match '85%'."""
        v = OutputValidator()
        result = v.validate(
            "系数 85%",
            [ToolResult(success=True, data={"coefficient": 0.85})],
        )
        # 0.85 does not auto-convert, so 85 is ungrounded
        assert result.status in ("warn", "fail")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_grounded.py::TestNumberToken -v`
Expected: FAIL — `NumberToken` doesn't exist yet

- [ ] **Step 3: Rewrite grounded.py with structured validation**

Full replacement of grounded.py (keeping DataSource and ValidationResult unchanged):

```python
"""Grounded generation layer — DataSource provenance + OutputValidator anti-hallucination."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DataSource:
    """Immutable provenance record attached to a ToolResult."""
    type: str
    table: str
    ref: str
    queried_at: str

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "table": self.table, "ref": self.ref, "queried_at": self.queried_at}


@dataclass
class ValidationResult:
    status: str  # "pass" | "warn" | "fail"
    ungrounded_values: list[float] = field(default_factory=list)
    contradictions: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class NumberToken:
    value: float
    unit: str       # "分"/"名"/"人"/"%"/"" etc.
    key_path: str   # "avg_score" / "" (from response text)


# Unit → tolerance mapping
_TOLERANCE: dict[str, float] = {
    "分": 0.005,   # 0.5% relative
    "名": 0.0,
    "人": 0.0,
    "个": 0.0,
    "次": 0.0,
    "所": 0.0,
    "班": 0.0,
    "科": 0.0,
    "题": 0.0,
    "道": 0.0,
    "%": 0.02,     # 2% relative
}
_DEFAULT_TOLERANCE = 0.05  # 5% for unknown units

_UNIT_LIST = "分|%|人|名|个|次|所|班|科|题|道"
_NUM_PATTERN = re.compile(rf'(\d+\.?\d*)\s*({_UNIT_LIST})')

_RATE_KEYWORDS = {"rate", "ratio", "percent", "及格", "优秀", "pass", "合格"}


class OutputValidator:
    """Post-generation validator: check response numbers against tool data."""

    def validate(self, response: str, tool_results: list) -> ValidationResult:
        if not tool_results:
            return ValidationResult(status="pass")

        response_tokens = self._extract_number_tokens(response)
        if not response_tokens:
            return ValidationResult(status="pass")

        tool_tokens: list[NumberToken] = []
        for tr in tool_results:
            if tr.data:
                self._collect_number_tokens(tr.data, tool_tokens)

        if not tool_tokens:
            return ValidationResult(status="pass")

        tool_values = {t.value for t in tool_tokens}
        ungrounded: list[float] = []
        contradictions: list[dict] = []

        for rt in response_tokens:
            tolerance = _TOLERANCE.get(rt.unit, _DEFAULT_TOLERANCE)
            if self._matches_any(rt.value, tool_values):
                continue
            closest = self._find_closest(rt.value, tool_values)
            if closest is not None:
                rel_err = abs(rt.value - closest) / max(abs(closest), 1)
                if rel_err <= tolerance:
                    continue  # within tolerance
                contradictions.append({"response": rt.value, "tool": closest, "unit": rt.unit})
            else:
                ungrounded.append(rt.value)

        if contradictions:
            return ValidationResult(status="fail", contradictions=contradictions)
        if ungrounded:
            return ValidationResult(status="warn", ungrounded_values=ungrounded)
        return ValidationResult(status="pass")

    def _extract_number_tokens(self, text: str) -> list[NumberToken]:
        seen: set[tuple[float, str]] = set()
        tokens: list[NumberToken] = []
        for m in _NUM_PATTERN.finditer(text):
            value = float(m.group(1))
            unit = m.group(2)
            key = (value, unit)
            if key not in seen:
                seen.add(key)
                tokens.append(NumberToken(value=value, unit=unit, key_path=""))
        return tokens

    def _collect_number_tokens(
        self,
        data: Any,
        result: list[NumberToken],
        key_path: str = "",
        depth: int = 0,
    ) -> None:
        if depth > 5:
            return
        if isinstance(data, (int, float)):
            result.append(NumberToken(value=float(data), unit="", key_path=key_path))
            # P2-2: conditional percent conversion
            if 0 < data < 1 and any(kw in key_path.lower() for kw in _RATE_KEYWORDS):
                result.append(NumberToken(value=round(data * 100, 2), unit="%", key_path=key_path))
        elif isinstance(data, dict):
            for k, v in data.items():
                self._collect_number_tokens(v, result, key_path=k, depth=depth + 1)
        elif isinstance(data, list):
            for item in data:
                self._collect_number_tokens(item, result, key_path=key_path, depth=depth + 1)

    def _matches_any(self, num: float, tool_values: set[float]) -> bool:
        return any(abs(num - tv) < 0.01 for tv in tool_values)

    def _find_closest(self, num: float, tool_values: set[float]) -> float | None:
        if not tool_values:
            return None
        return min(tool_values, key=lambda x: abs(x - num))
```

- [ ] **Step 4: Run all grounded tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_grounded.py -v`
Expected: All PASS (new + existing)

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/ai/grounded.py tests/test_ai/test_grounded.py
git commit -m "feat(ai): OutputValidator 结构化 — NumberToken + 分类型容差 + 百分数条件转换"
```

**审查清单:**
- ✓ NumberToken(value, unit, key_path) 结构化提取
- ✓ 分/名/人等计数类零容差，%类 2%，默认 5%
- ✓ 百分数转换只在 key_path 含 rate/ratio/percent 时执行
- ✓ 现有 DataSource/ValidationResult 接口不变
- ✗ 反向: 旧代码统一 25% 容差 + 无条件百分数转换

---

### Task 8: 循环检测

**Files:**
- Modify: `src/edu_cloud/ai/agent_loop.py:151-191`
- Test: `tests/test_ai/test_agent_loop.py` (追加测试)

- [ ] **Step 1: Write tests for loop detection**

```python
# tests/test_ai/test_agent_loop.py — 追加

import json


class TestLoopDetection:
    """P2-3: detect and skip duplicate tool calls."""

    def test_canonicalize_sorts_keys(self):
        from edu_cloud.ai.agent_loop import _canonicalize
        assert _canonicalize({"b": 1, "a": 2}) == {"a": 2, "b": 1}

    def test_canonicalize_nested(self):
        from edu_cloud.ai.agent_loop import _canonicalize
        result = _canonicalize({"z": {"b": 1, "a": 2}})
        assert list(result["z"].keys()) == ["a", "b"]

    def test_fingerprint_stable(self):
        from edu_cloud.ai.agent_loop import _canonicalize
        a = json.dumps(_canonicalize({"exam_id": "e1", "class_id": "c1"}), ensure_ascii=False, sort_keys=True)
        b = json.dumps(_canonicalize({"class_id": "c1", "exam_id": "e1"}), ensure_ascii=False, sort_keys=True)
        assert a == b


class TestLoopDetectionBehavior:
    """P2-3: behavioral tests for loop detection skip/no-skip scenarios."""

    def test_consecutive_same_error_triggers_skip(self):
        """3 consecutive calls with same name+params+error → 3rd should be skipped."""
        from edu_cloud.ai.agent_loop import AgentState, _canonicalize
        from edu_cloud.ai.schemas import Message, ToolCall
        import json as _json

        state = AgentState(messages=[])
        fp = _json.dumps(_canonicalize({"exam_id": "e1"}), ensure_ascii=False, sort_keys=True)

        # Simulate 2 prior consecutive failures with same error
        state._recent_calls.append(("get_scores", fp, "not found"))
        state._recent_calls.append(("get_scores", fp, "not found"))

        # 3rd call should be detected
        tc = ToolCall(id="3", name="get_scores", arguments={"exam_id": "e1"}, _raw={})
        consecutive_fails = 0
        last_error = None
        for name, args_fp, err in reversed(state._recent_calls):
            if name == tc.name and args_fp == fp and err:
                if last_error is None:
                    last_error = err
                if err == last_error:
                    consecutive_fails += 1
                else:
                    break
            else:
                break
        assert consecutive_fails >= 2, "Should detect consecutive duplicate failures"

    def test_success_breaks_chain(self):
        """Success between failures should break consecutive chain → no skip."""
        from edu_cloud.ai.agent_loop import AgentState, _canonicalize
        from edu_cloud.ai.schemas import ToolCall
        import json as _json

        state = AgentState(messages=[])
        fp = _json.dumps(_canonicalize({"exam_id": "e1"}), ensure_ascii=False, sort_keys=True)

        # fail → success → fail (not consecutive)
        state._recent_calls.append(("get_scores", fp, "not found"))
        state._recent_calls.append(("get_scores", fp, ""))  # success (empty error)
        state._recent_calls.append(("get_scores", fp, "not found"))

        tc = ToolCall(id="4", name="get_scores", arguments={"exam_id": "e1"}, _raw={})
        consecutive_fails = 0
        last_error = None
        for name, args_fp, err in reversed(state._recent_calls):
            if name == tc.name and args_fp == fp and err:
                if last_error is None:
                    last_error = err
                if err == last_error:
                    consecutive_fails += 1
                else:
                    break
            else:
                break
        assert consecutive_fails < 2, "Success should break consecutive chain"

    def test_different_error_breaks_chain(self):
        """Different error texts should break consecutive chain."""
        from edu_cloud.ai.agent_loop import AgentState, _canonicalize
        from edu_cloud.ai.schemas import ToolCall
        import json as _json

        state = AgentState(messages=[])
        fp = _json.dumps(_canonicalize({"exam_id": "e1"}), ensure_ascii=False, sort_keys=True)

        state._recent_calls.append(("get_scores", fp, "timeout"))
        state._recent_calls.append(("get_scores", fp, "not found"))  # different error

        tc = ToolCall(id="5", name="get_scores", arguments={"exam_id": "e1"}, _raw={})
        consecutive_fails = 0
        last_error = None
        for name, args_fp, err in reversed(state._recent_calls):
            if name == tc.name and args_fp == fp and err:
                if last_error is None:
                    last_error = err
                if err == last_error:
                    consecutive_fails += 1
                else:
                    break
            else:
                break
        assert consecutive_fails < 2, "Different errors should break chain"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_agent_loop.py::TestLoopDetection -v`
Expected: FAIL — `_canonicalize` doesn't exist

- [ ] **Step 3: Add _canonicalize function and loop detection state to agent_loop.py**

Add at module level (after imports):

```python
import json as _json

def _canonicalize(value: Any) -> Any:
    """Canonicalize dict keys for fingerprinting."""
    if isinstance(value, dict):
        return {k: _canonicalize(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [_canonicalize(v) for v in value]
    return value
```

Add to AgentState:

```python
    _recent_calls: list[tuple[str, str, str]] = field(default_factory=list)
    # Each entry: (tool_name, args_fingerprint, error_text_or_empty)
```

Add loop detection in the tool execution section (after `for tc in resp.tool_calls:` yield tool_call events, before executing):

```python
                    # P2-3: loop detection — check for CONSECUTIVE duplicate failed calls
                    # Design §4 requires ALL 4 conditions: same name + same params + consecutive + same error
                    skipped_ids: set[str] = set()
                    for tc in resp.tool_calls:
                        fp = _json.dumps(_canonicalize(tc.arguments), ensure_ascii=False, sort_keys=True)
                        # Check last N entries for CONSECUTIVE matching with SAME error text
                        consecutive_fails = 0
                        last_error = None
                        for name, args_fp, err in reversed(state._recent_calls):
                            if name == tc.name and args_fp == fp and err:
                                if last_error is None:
                                    last_error = err
                                if err == last_error:
                                    consecutive_fails += 1
                                else:
                                    break  # different error text — not same failure
                            else:
                                break  # chain broken — not consecutive
                        if consecutive_fails >= 2:
                            skipped_ids.add(tc.id)
                            state.messages.append(Message(
                                role="tool",
                                content='{"success": false, "error": "skipped: duplicate tool call"}',
                                tool_call_id=tc.id,
                                name=tc.name,
                            ))
                            yield AgentEvent(type="tool_result", data={
                                "tool": tc.name, "result": {"error": "skipped: duplicate tool call"},
                            })
```

Filter skipped calls before execution and update recent_calls after:

```python
                    # Filter out skipped calls
                    active_calls = [tc for tc in resp.tool_calls if tc.id not in skipped_ids]
```

After tool results, update `_recent_calls`:

```python
                    for tc, result in zip(active_calls, results):
                        fp = _json.dumps(_canonicalize(tc.arguments), ensure_ascii=False, sort_keys=True)
                        error_text = result.error if (not result.success and result.error) else ""
                        state._recent_calls.append((tc.name, fp, error_text))
                        if len(state._recent_calls) > 9:
                            state._recent_calls = state._recent_calls[-9:]
```

- [ ] **Step 4: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_agent_loop.py::TestLoopDetection -v`
Expected: All PASS

- [ ] **Step 5: Run full agent_loop tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_agent_loop.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/ai/agent_loop.py tests/test_ai/test_agent_loop.py
git commit -m "feat(ai): 循环检测 — 相同工具+参数连续 3 次调用自动跳过"
```

**审查清单:**
- ✓ _canonicalize 递归排序 dict keys
- ✓ 连续 3 次相同 tool+参数 → 跳过并返回 tool role 消息
- ✓ 不新增事件类型（复用 tool_result 形状，守 INV-3）
- ✗ 反向: 无检测时相同失败工具无限重试

**边界条件:**
- 同工具不同参数（分页查询）→ fingerprint 不同，不触发
- 同工具同参数但上次成功 → _recent_calls 记录无 error，不匹配连续失败
- recent_calls 最多保留 9 条 → 防内存增长

---

### Task 9: Tier 阈值配置外提

**Files:**
- Modify: `src/edu_cloud/config.py:53+`
- Modify: `src/edu_cloud/ai/capability_probe.py:12-13, 39-41, 59-61`
- Test: `tests/test_ai/test_capability_probe.py` (追加测试)

- [ ] **Step 1: Write test — 自定义阈值应生效**

```python
# tests/test_ai/test_capability_probe.py — 追加

import pytest
from unittest.mock import AsyncMock, MagicMock
from edu_cloud.ai.capability_probe import CapabilityProbe
from edu_cloud.ai.llm_adapter import LLMProxyAdapter


class TestConfigurableThresholds:
    """P3-1: tier thresholds should be configurable via public API."""

    @pytest.mark.asyncio
    async def test_custom_t1_threshold_affects_determine_tier(self):
        """Lower T1 threshold should promote 50K context model to tier 1."""
        probe = CapabilityProbe(tier_thresholds=[50_000, 10_000])
        adapter = MagicMock(spec=LLMProxyAdapter)
        adapter.context_window_size.return_value = 60_000
        adapter.set_capabilities = MagicMock()
        # Mock tool_use test to succeed
        probe._test_tool_use = AsyncMock(return_value=True)

        tier = await probe.determine_tier(adapter)
        assert tier == 1, "60K context should be tier 1 with custom threshold [50K, 10K]"

    @pytest.mark.asyncio
    async def test_default_threshold_keeps_50k_as_tier2(self):
        """With default thresholds, 50K context is tier 2 (not tier 1)."""
        probe = CapabilityProbe()
        adapter = MagicMock(spec=LLMProxyAdapter)
        adapter.context_window_size.return_value = 60_000
        adapter.set_capabilities = MagicMock()
        probe._test_tool_use = AsyncMock(return_value=True)

        tier = await probe.determine_tier(adapter)
        assert tier == 2, "60K context should be tier 2 with default threshold [100K, 30K]"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_capability_probe.py::TestConfigurableThresholds -v`
Expected: FAIL — CapabilityProbe doesn't accept tier_thresholds

- [ ] **Step 3: Add config and update CapabilityProbe**

In `config.py`, add after `LLM_MAX_RETRIES`:

```python
    # AI Agent — capability tiers
    TIER_CONTEXT_THRESHOLDS: list[int] = [100_000, 30_000]
```

In `capability_probe.py`, update:

```python
class CapabilityProbe:
    def __init__(self, tier_thresholds: list[int] | None = None):
        from edu_cloud.config import settings
        self._tier_thresholds = tier_thresholds or settings.TIER_CONTEXT_THRESHOLDS
        self._override: int | None = None
        self._cached_tier: int | None = None
```

Replace hardcoded constants in `determine_tier`:

```python
        if has_tool_use and context_window >= self._tier_thresholds[0]:
            tier = 1
        elif has_tool_use and context_window >= self._tier_thresholds[1]:
            tier = 2
        else:
            tier = 3
```

Remove module-level `TIER_1_MIN_CONTEXT` and `TIER_2_MIN_CONTEXT`.

- [ ] **Step 4: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_capability_probe.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/config.py src/edu_cloud/ai/capability_probe.py tests/test_ai/test_capability_probe.py
git commit -m "feat(ai): Tier 阈值配置外提 — TIER_CONTEXT_THRESHOLDS 移到 Settings"
```

---

### Task 10: Router 关键词配置外提

**Files:**
- Modify: `src/edu_cloud/config.py`
- Modify: `src/edu_cloud/ai/model_router.py:14-17, 20-21`
- Test: `tests/test_ai/test_model_router.py` (追加测试)

- [ ] **Step 1: Write test — 自定义关键词应生效**

```python
# tests/test_ai/test_model_router.py — 追加

from unittest.mock import MagicMock
from edu_cloud.ai.model_router import ModelRouter


class TestConfigurableKeywords:
    """P3-2: enhance keywords should be configurable via public route() API."""

    def test_custom_keywords_affects_route_decision(self):
        """Custom keyword should trigger 'advanced' tier via route()."""
        router = ModelRouter(enhance_keywords=["自定义词"])
        user_slots = [MagicMock()]
        system_slots = [MagicMock()]

        result = router.route("请自定义词处理", user_slots, system_slots, enhanced_enabled=True)
        assert result.tier == "advanced", "Custom keyword should route to advanced"

    def test_custom_keywords_non_match_stays_standard(self):
        """Non-matching message stays standard."""
        router = ModelRouter(enhance_keywords=["自定义词"])
        user_slots = [MagicMock()]
        system_slots = [MagicMock()]

        result = router.route("普通问题", user_slots, system_slots, enhanced_enabled=True)
        assert result.tier == "standard"

    def test_default_keywords_route_analysis(self):
        """Default keywords should route '分析' to advanced via route()."""
        router = ModelRouter()
        user_slots = [MagicMock()]
        system_slots = [MagicMock()]

        result = router.route("请分析数据", user_slots, system_slots, enhanced_enabled=True)
        assert result.tier == "advanced"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_model_router.py::TestConfigurableKeywords -v`
Expected: FAIL — ModelRouter doesn't accept enhance_keywords

- [ ] **Step 3: Add config and update ModelRouter**

In `config.py`, add after `TIER_CONTEXT_THRESHOLDS`:

```python
    MODEL_ROUTER_ADVANCED_KEYWORDS: list[str] | None = None
```

In `model_router.py`:

```python
_DEFAULT_ENHANCE_KEYWORDS = [
    "分析", "报告", "对比", "趋势", "诊断", "评估",
    "预测", "建议", "规划", "总结", "深度",
]


class ModelRouter:
    def __init__(self, enhance_keywords: list[str] | None = None):
        from edu_cloud.config import settings
        self._keywords = enhance_keywords or settings.MODEL_ROUTER_ADVANCED_KEYWORDS or _DEFAULT_ENHANCE_KEYWORDS
        import logging
        logging.getLogger(__name__).info("ModelRouter: %d enhance keywords active", len(self._keywords))

    def _needs_enhancement(self, message: str) -> bool:
        if not message:
            return False
        return any(kw in message for kw in self._keywords)
```

Remove old `_ENHANCE_KEYWORDS` module-level list.

- [ ] **Step 4: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_model_router.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/config.py src/edu_cloud/ai/model_router.py tests/test_ai/test_model_router.py
git commit -m "feat(ai): Router 关键词配置外提 — Settings 覆盖 + 代码常量 fallback"
```

---

### Task 11: 全量回归测试

**Files:**
- No code changes

- [ ] **Step 1: Run full backend test suite**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Expected: 1359+ tests PASS (new tests added, no regressions)

- [ ] **Step 2: Verify INV-3 — SSE event format unchanged via existing contract tests**

Run existing payload shape tests (these assert exact `tool_result`/`tool_call` key structure):

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_ai_api_v2.py::test_sse_event_exact_payload_shape tests/test_ai/test_agent_loop.py::test_basic_tool_loop -v`
Expected: All PASS — event payload shapes `{"tool": ..., "result": ...}` unchanged

- [ ] **Step 3: Commit tag**

```bash
git tag -a v-resilience-complete -m "Agent 韧性与验证增强完成 — 11 Tasks"
```

**审查清单:**
- ✓ INV-1: DataScope 行为不变
- ✓ INV-2: 42 工具签名不变
- ✓ INV-3: SSE 事件格式不变
- ✓ INV-4: 全量测试通过
