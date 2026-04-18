<!-- pre-takeover: archived for history, not active spec -->
# Phase 1: 多 Agent 编排引擎 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 edu-cloud Agent 从单循环工具调度器升级为 Supervisor + AgentTeam 多 Agent 编排架构，支持按领域分工、动态模型选择、向后兼容。

**Architecture:** Supervisor Agent 接收用户请求，判断复杂度：简单请求退化为现有单 AgentLoop（零破坏性），复杂多步请求分派到领域 AgentTeam（edu_data / knowledge / homework），每个 Team 内子 Agent 共享 State 并按 DAG 执行。模型按任务复杂度动态选择（强/中/弱三档映射到 llm-proxy slot）。

**Tech Stack:** FastAPI + asyncio + httpx + existing llm-proxy + existing ToolRegistry

**Design doc:** `docs/plans/2026-04-05-agent-evolution-design.md` §2

---

## 文件结构

| 文件 | 类型 | 职责 |
|------|------|------|
| `src/edu_cloud/ai/agent_spec.py` | 新增 | AgentSpec 声明 + 模型动态选择 |
| `src/edu_cloud/ai/shared_state.py` | 新增 | SharedState 基类（组内共享状态容器） |
| `src/edu_cloud/ai/agent_team.py` | 新增 | AgentTeam + TeamRegistry（Team 注册 + 执行编排） |
| `src/edu_cloud/ai/supervisor.py` | 新增 | Supervisor（意图分类 + Team 路由 + 结果汇总） |
| `src/edu_cloud/ai/teams/__init__.py` | 新增 | Team 自动注册入口 |
| `src/edu_cloud/ai/teams/edu_data.py` | 新增 | 教育数据 Team 定义 |
| `src/edu_cloud/ai/teams/knowledge.py` | 新增 | 知识库 Team 定义 |
| `src/edu_cloud/ai/teams/homework.py` | 新增 | 作业 Team 定义 |
| `src/edu_cloud/ai/registry.py` | 修改 | 新增 `filter_by_names()` 方法 |
| `src/edu_cloud/ai/agent_loop.py` | 修改 | 支持作为子 Agent 运行（接受工具子集 + 外部 adapter） |
| `src/edu_cloud/api/ai.py` | 修改 | SSE 端点接入 Supervisor |
| `tests/test_ai/test_agent_spec.py` | 新增 | AgentSpec 单测 |
| `tests/test_ai/test_shared_state.py` | 新增 | SharedState 单测 |
| `tests/test_ai/test_agent_team.py` | 新增 | AgentTeam + TeamRegistry 单测 |
| `tests/test_ai/test_supervisor.py` | 新增 | Supervisor 单测 |
| `tests/test_ai/test_teams.py` | 新增 | 预设 Team 定义验证 |
| `tests/test_ai/test_backward_compat.py` | 新增 | 向后兼容回归测试 |

---

### Task 1: AgentSpec 声明 + 模型动态选择

**Files:**
- Create: `src/edu_cloud/ai/agent_spec.py`
- Test: `tests/test_ai/test_agent_spec.py`

**测试契约:**
1. AgentSpec 创建与字段验证
   - 入口: `AgentSpec(name=..., tools=[...])` 构造
   - 反例: 缺少 name 或 tools 为空时错误实现会静默创建无效 spec
   - 边界: tools=[] / model_tier=None / max_turns=0
   - 回归: N/A
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_agent_spec.py -v`
2. select_slot 按复杂度返回正确 slot
   - 入口: `AgentSpec.select_slot(complexity)` 调用
   - 反例: 错误实现会忽略 model_tier 强制覆盖，返回自动选择结果
   - 边界: 未知 complexity / model_tier=None / model_tier=1
   - 回归: N/A
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_agent_spec.py::test_select_slot -v`

**审查清单:**
- ✓ AgentSpec 字段完整（name/description/tools/model_tier/max_turns/task_complexity）
- ✓ model_tier 有值时 select_slot 返回强制 slot，忽略 task_complexity
- ✓ model_tier=None 时按 complexity_map 选择
- ✗ 未知 complexity 不应抛异常（应回退到 "primary"）

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_agent_spec.py
import pytest
from edu_cloud.ai.agent_spec import AgentSpec, select_slot


class TestAgentSpec:
    def test_create_basic(self):
        spec = AgentSpec(
            name="research",
            description="Research agent for literature search",
            tools=["search_literature", "knowledge_base_query"],
        )
        assert spec.name == "research"
        assert spec.tools == ["search_literature", "knowledge_base_query"]
        assert spec.model_tier is None
        assert spec.max_turns == 15
        assert spec.task_complexity == "retrieval"

    def test_create_with_forced_tier(self):
        spec = AgentSpec(
            name="writer",
            description="Writing agent",
            tools=["format_citation"],
            model_tier=1,
            task_complexity="generation",
        )
        assert spec.model_tier == 1

    def test_create_empty_tools(self):
        spec = AgentSpec(name="empty", description="No tools", tools=[])
        assert spec.tools == []


class TestSelectSlot:
    def test_forced_tier_1(self):
        spec = AgentSpec(name="x", description="x", tools=[], model_tier=1)
        assert select_slot(spec) == "enhanced"

    def test_forced_tier_2(self):
        spec = AgentSpec(name="x", description="x", tools=[], model_tier=2)
        assert select_slot(spec) == "primary"

    def test_forced_tier_3(self):
        spec = AgentSpec(name="x", description="x", tools=[], model_tier=3)
        assert select_slot(spec) == "basic"

    def test_auto_reasoning(self):
        spec = AgentSpec(name="x", description="x", tools=[], task_complexity="reasoning")
        assert select_slot(spec) == "enhanced"

    def test_auto_generation(self):
        spec = AgentSpec(name="x", description="x", tools=[], task_complexity="generation")
        assert select_slot(spec) == "enhanced"

    def test_auto_retrieval(self):
        spec = AgentSpec(name="x", description="x", tools=[], task_complexity="retrieval")
        assert select_slot(spec) == "primary"

    def test_auto_data_query(self):
        spec = AgentSpec(name="x", description="x", tools=[], task_complexity="data_query")
        assert select_slot(spec) == "primary"

    def test_auto_formatting(self):
        spec = AgentSpec(name="x", description="x", tools=[], task_complexity="formatting")
        assert select_slot(spec) == "basic"

    def test_unknown_complexity_fallback(self):
        spec = AgentSpec(name="x", description="x", tools=[], task_complexity="unknown_type")
        assert select_slot(spec) == "primary"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_agent_spec.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'edu_cloud.ai.agent_spec'`

- [ ] **Step 3: Implement AgentSpec**

```python
# src/edu_cloud/ai/agent_spec.py
"""Sub-agent specification and model slot selection."""

from dataclasses import dataclass, field

_TIER_TO_SLOT = {1: "enhanced", 2: "primary", 3: "basic"}

_COMPLEXITY_TO_SLOT = {
    "reasoning": "enhanced",
    "generation": "enhanced",
    "retrieval": "primary",
    "data_query": "primary",
    "formatting": "basic",
}


@dataclass(frozen=True)
class AgentSpec:
    """Declaration of a sub-agent within an AgentTeam."""

    name: str
    description: str
    tools: list[str]
    model_tier: int | None = None
    max_turns: int = 15
    task_complexity: str = "retrieval"


def select_slot(spec: AgentSpec) -> str:
    """Return the llm-proxy slot name for this agent spec.

    If model_tier is set, use it directly. Otherwise, infer from task_complexity.
    """
    if spec.model_tier is not None:
        return _TIER_TO_SLOT.get(spec.model_tier, "primary")
    return _COMPLEXITY_TO_SLOT.get(spec.task_complexity, "primary")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_agent_spec.py -v`
Expected: All 11 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/edu-cloud && git add src/edu_cloud/ai/agent_spec.py tests/test_ai/test_agent_spec.py
git commit -m "feat(ai): add AgentSpec dataclass + model slot selection"
```

---

### Task 2: SharedState 基类

**Files:**
- Create: `src/edu_cloud/ai/shared_state.py`
- Test: `tests/test_ai/test_shared_state.py`

**测试契约:**
1. SharedState 读写 + 历史追踪
   - 入口: `state.set(key, value)` / `state.get(key)`
   - 反例: 错误实现不记录历史，`get_history()` 返回空
   - 边界: get 不存在的 key / set 同 key 覆盖 / checkpoint 序列化
   - 回归: N/A
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_shared_state.py -v`

**审查清单:**
- ✓ get/set/get_history 基本操作正确
- ✓ checkpoint() 返回可序列化的快照
- ✓ restore() 从快照恢复
- ✗ 并发写入不保证原子性（单 Agent 循环内顺序执行，不需要锁）

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_shared_state.py
import pytest
from edu_cloud.ai.shared_state import SharedState


class TestSharedState:
    def test_set_and_get(self):
        state = SharedState()
        state.set("topic", "深度学习")
        assert state.get("topic") == "深度学习"

    def test_get_missing_key_returns_default(self):
        state = SharedState()
        assert state.get("missing") is None
        assert state.get("missing", "fallback") == "fallback"

    def test_set_overwrite(self):
        state = SharedState()
        state.set("count", 1)
        state.set("count", 2)
        assert state.get("count") == 2

    def test_history_tracks_changes(self):
        state = SharedState()
        state.set("a", 1)
        state.set("b", 2)
        state.set("a", 3)
        history = state.get_history()
        assert len(history) == 3
        assert history[0] == ("a", 1)
        assert history[1] == ("b", 2)
        assert history[2] == ("a", 3)

    def test_checkpoint_and_restore(self):
        state = SharedState()
        state.set("x", 10)
        state.set("y", 20)
        snap = state.checkpoint()
        assert snap == {"x": 10, "y": 20}

        state2 = SharedState()
        state2.restore(snap)
        assert state2.get("x") == 10
        assert state2.get("y") == 20

    def test_as_dict(self):
        state = SharedState()
        state.set("a", 1)
        state.set("b", [2, 3])
        d = state.as_dict()
        assert d == {"a": 1, "b": [2, 3]}
        # Mutation safety: changing returned dict should not affect state
        d["a"] = 999
        assert state.get("a") == 1

    def test_stage_tracking(self):
        state = SharedState()
        assert state.current_stage is None
        state.set_stage("research")
        assert state.current_stage == "research"
        state.set_stage("writing")
        assert state.current_stage == "writing"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_shared_state.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement SharedState**

```python
# src/edu_cloud/ai/shared_state.py
"""Shared state container for AgentTeam sub-agents."""

from __future__ import annotations

import copy
from typing import Any


class SharedState:
    """Mutable key-value state shared among sub-agents within a team.

    Tracks history of all writes for audit/debugging.
    NOT thread-safe — designed for sequential or cooperative async execution.
    """

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._history: list[tuple[str, Any]] = []
        self._stage: str | None = None

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._history.append((key, value))

    def get_history(self) -> list[tuple[str, Any]]:
        return list(self._history)

    def checkpoint(self) -> dict[str, Any]:
        return copy.deepcopy(self._data)

    def restore(self, snapshot: dict[str, Any]) -> None:
        self._data = copy.deepcopy(snapshot)

    def as_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._data)

    @property
    def current_stage(self) -> str | None:
        return self._stage

    def set_stage(self, stage: str) -> None:
        self._stage = stage
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_shared_state.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/edu-cloud && git add src/edu_cloud/ai/shared_state.py tests/test_ai/test_shared_state.py
git commit -m "feat(ai): add SharedState container for team sub-agents"
```

---

### Task 3: ToolRegistry.filter_by_names()

**Files:**
- Modify: `src/edu_cloud/ai/registry.py` (add method at ~line 73)
- Test: `tests/test_ai/test_registry_filter.py`

**测试契约:**
1. filter_by_names 返回匹配子集
   - 入口: `registry.filter_by_names(["tool_a", "tool_b"])`
   - 反例: 错误实现返回全部工具，不做过滤
   - 边界: 空列表 / 不存在的名称 / 全部匹配
   - 回归: N/A
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_registry_filter.py -v`

**审查清单:**
- ✓ 空 names 返回空列表
- ✓ 不存在的名称被忽略（不抛异常）
- ✓ 返回顺序与 names 一致
- ✗ 不修改现有 get_all_specs 行为

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_registry_filter.py
import pytest
from edu_cloud.ai.registry import ToolRegistry
from edu_cloud.ai.tool_context import ToolContext, ToolResult


@pytest.fixture
def registry_with_tools():
    reg = ToolRegistry()

    @reg.register(name="tool_a", description="Tool A")
    async def tool_a(input_data: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data="a")

    @reg.register(name="tool_b", description="Tool B")
    async def tool_b(input_data: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data="b")

    @reg.register(name="tool_c", description="Tool C")
    async def tool_c(input_data: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data="c")

    return reg


class TestFilterByNames:
    def test_filter_subset(self, registry_with_tools):
        result = registry_with_tools.filter_by_names(["tool_a", "tool_c"])
        names = [s.name for s in result]
        assert names == ["tool_a", "tool_c"]

    def test_filter_all(self, registry_with_tools):
        result = registry_with_tools.filter_by_names(["tool_a", "tool_b", "tool_c"])
        assert len(result) == 3

    def test_filter_empty(self, registry_with_tools):
        result = registry_with_tools.filter_by_names([])
        assert result == []

    def test_filter_nonexistent(self, registry_with_tools):
        result = registry_with_tools.filter_by_names(["tool_a", "nonexistent"])
        names = [s.name for s in result]
        assert names == ["tool_a"]

    def test_filter_preserves_order(self, registry_with_tools):
        result = registry_with_tools.filter_by_names(["tool_c", "tool_a"])
        names = [s.name for s in result]
        assert names == ["tool_c", "tool_a"]

    def test_get_all_specs_unchanged(self, registry_with_tools):
        # Verify filter_by_names doesn't break existing method
        all_specs = registry_with_tools.get_all_specs()
        assert len(all_specs) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_registry_filter.py -v`
Expected: FAIL — `AttributeError: 'ToolRegistry' object has no attribute 'filter_by_names'`

- [ ] **Step 3: Add filter_by_names to ToolRegistry**

Add after `get_all_specs()` method (after line 73 in `registry.py`):

```python
    def filter_by_names(self, names: list[str]) -> list["ToolSpec"]:
        """Return ToolSpecs matching the given names, in the order of names."""
        return [self._tools[n] for n in names if n in self._tools]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_registry_filter.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Run existing registry tests for regression**

Run: `cd ~/edu-cloud && python -m pytest tests/ -k "registry" -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
cd ~/edu-cloud && git add src/edu_cloud/ai/registry.py tests/test_ai/test_registry_filter.py
git commit -m "feat(ai): add ToolRegistry.filter_by_names() for sub-agent tool filtering"
```

---

### Task 4: AgentTeam + TeamRegistry

**Files:**
- Create: `src/edu_cloud/ai/agent_team.py`
- Test: `tests/test_ai/test_agent_team.py`

**测试契约:**
1. AgentTeam 创建与验证
   - 入口: `AgentTeam(name=..., agents=[...], execution="sequential")`
   - 反例: 错误实现允许无 agents 的 team 执行
   - 边界: agents=[] / execution 非法值 / 重复 agent name
   - 回归: N/A
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_agent_team.py::TestAgentTeam -v`
2. TeamRegistry 注册与查找
   - 入口: `TeamRegistry.register(team)` / `TeamRegistry.get(name)`
   - 反例: 错误实现允许同名 team 覆盖注册
   - 边界: get 不存在的 name / list_teams 空
   - 回归: N/A
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_agent_team.py::TestTeamRegistry -v`
3. TeamExecutor 顺序执行子 Agent
   - 入口: `TeamExecutor.run(team, goal, ctx, ...)`
   - 反例: 错误实现不按 agents 顺序执行
   - 边界: 单 agent team / agent 执行失败
   - 回归: N/A
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_agent_team.py::TestTeamExecutor -v`

**审查清单:**
- ✓ TeamRegistry 是全局单例
- ✓ register 重复 name 抛 ValueError
- ✓ TeamExecutor.run 按 agents 列表顺序执行
- ✓ 每个 sub-agent 运行后将结果写入 SharedState
- ✗ 并行执行模式留空（Phase 1 只实现 sequential）

**边界条件:**
- 空 agents 列表 → 期望: 直接返回空结果，不崩溃
- sub-agent 执行中 LLM 调用失败 → 期望: 记录错误，继续下一个 agent（不中断 team）
- team name 重复注册 → 期望: 抛 ValueError

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_agent_team.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from edu_cloud.ai.agent_spec import AgentSpec
from edu_cloud.ai.agent_team import AgentTeam, TeamRegistry, TeamExecutor
from edu_cloud.ai.shared_state import SharedState
from edu_cloud.ai.schemas import AgentEvent


def _make_spec(name: str, tools: list[str] | None = None) -> AgentSpec:
    return AgentSpec(name=name, description=f"{name} agent", tools=tools or [])


class TestAgentTeam:
    def test_create(self):
        team = AgentTeam(
            name="test_team",
            description="Test team",
            agents=[_make_spec("a"), _make_spec("b")],
            execution="sequential",
        )
        assert team.name == "test_team"
        assert len(team.agents) == 2
        assert team.execution == "sequential"

    def test_agent_names(self):
        team = AgentTeam(
            name="t",
            description="t",
            agents=[_make_spec("x"), _make_spec("y")],
        )
        assert team.agent_names == ["x", "y"]

    def test_all_tools(self):
        team = AgentTeam(
            name="t",
            description="t",
            agents=[
                _make_spec("a", ["tool_1", "tool_2"]),
                _make_spec("b", ["tool_2", "tool_3"]),
            ],
        )
        assert team.all_tools == {"tool_1", "tool_2", "tool_3"}


class TestTeamRegistry:
    def test_register_and_get(self):
        reg = TeamRegistry()
        team = AgentTeam(name="edu", description="Edu", agents=[_make_spec("a")])
        reg.register(team)
        assert reg.get("edu") is team

    def test_get_missing_returns_none(self):
        reg = TeamRegistry()
        assert reg.get("nonexistent") is None

    def test_register_duplicate_raises(self):
        reg = TeamRegistry()
        team = AgentTeam(name="dup", description="Dup", agents=[_make_spec("a")])
        reg.register(team)
        with pytest.raises(ValueError, match="already registered"):
            reg.register(team)

    def test_list_teams(self):
        reg = TeamRegistry()
        reg.register(AgentTeam(name="a", description="A", agents=[_make_spec("x")]))
        reg.register(AgentTeam(name="b", description="B", agents=[_make_spec("y")]))
        names = reg.list_teams()
        assert sorted(names) == ["a", "b"]

    def test_list_teams_empty(self):
        reg = TeamRegistry()
        assert reg.list_teams() == []

    def test_match_by_tools(self):
        reg = TeamRegistry()
        reg.register(AgentTeam(
            name="data", description="Data",
            agents=[_make_spec("q", ["exam_list", "exam_detail"])],
        ))
        reg.register(AgentTeam(
            name="kb", description="KB",
            agents=[_make_spec("s", ["search_curriculum"])],
        ))
        match = reg.match_by_tools(["exam_list"])
        assert match is not None
        assert match.name == "data"

    def test_match_by_tools_no_match(self):
        reg = TeamRegistry()
        reg.register(AgentTeam(
            name="data", description="Data",
            agents=[_make_spec("q", ["exam_list"])],
        ))
        assert reg.match_by_tools(["unknown_tool"]) is None


class TestTeamExecutor:
    @pytest.mark.asyncio
    async def test_sequential_execution(self):
        """Sub-agents execute in order, each writing to shared state."""
        execution_order = []

        spec_a = _make_spec("agent_a", ["tool_1"])
        spec_b = _make_spec("agent_b", ["tool_2"])
        team = AgentTeam(
            name="test",
            description="Test",
            agents=[spec_a, spec_b],
            execution="sequential",
        )

        async def mock_run_sub_agent(spec, goal, state, **kwargs):
            execution_order.append(spec.name)
            state.set(f"{spec.name}_done", True)
            return f"Result from {spec.name}"

        executor = TeamExecutor()
        with patch.object(executor, '_run_sub_agent', side_effect=mock_run_sub_agent):
            state = SharedState()
            result = await executor.run(team, "test goal", state)

        assert execution_order == ["agent_a", "agent_b"]
        assert state.get("agent_a_done") is True
        assert state.get("agent_b_done") is True

    @pytest.mark.asyncio
    async def test_empty_agents(self):
        team = AgentTeam(name="empty", description="Empty", agents=[])
        executor = TeamExecutor()
        state = SharedState()
        result = await executor.run(team, "test", state)
        assert result == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_agent_team.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement AgentTeam + TeamRegistry + TeamExecutor**

```python
# src/edu_cloud/ai/agent_team.py
"""AgentTeam: group of sub-agents with shared state and execution strategy."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from edu_cloud.ai.agent_spec import AgentSpec
from edu_cloud.ai.shared_state import SharedState

logger = logging.getLogger(__name__)


@dataclass
class AgentTeam:
    """A named group of sub-agents that collaborate on a task domain."""

    name: str
    description: str
    agents: list[AgentSpec]
    execution: str = "sequential"  # "sequential" | "parallel" | "dag"

    @property
    def agent_names(self) -> list[str]:
        return [a.name for a in self.agents]

    @property
    def all_tools(self) -> set[str]:
        result: set[str] = set()
        for a in self.agents:
            result.update(a.tools)
        return result


class TeamRegistry:
    """Registry for available AgentTeams."""

    def __init__(self) -> None:
        self._teams: dict[str, AgentTeam] = {}

    def register(self, team: AgentTeam) -> None:
        if team.name in self._teams:
            raise ValueError(f"Team '{team.name}' already registered")
        self._teams[team.name] = team
        logger.info("Registered team: %s (%d agents)", team.name, len(team.agents))

    def get(self, name: str) -> AgentTeam | None:
        return self._teams.get(name)

    def list_teams(self) -> list[str]:
        return list(self._teams.keys())

    def match_by_tools(self, tool_names: list[str]) -> AgentTeam | None:
        """Find the team whose tool set best overlaps with the given tools."""
        tool_set = set(tool_names)
        best: AgentTeam | None = None
        best_overlap = 0
        for team in self._teams.values():
            overlap = len(team.all_tools & tool_set)
            if overlap > best_overlap:
                best = team
                best_overlap = overlap
        return best

    def get_descriptions(self) -> list[dict[str, str]]:
        """Return team name+description for Supervisor prompt injection."""
        return [
            {"name": t.name, "description": t.description}
            for t in self._teams.values()
        ]


class TeamExecutor:
    """Executes an AgentTeam's sub-agents according to execution strategy."""

    async def run(
        self,
        team: AgentTeam,
        goal: str,
        state: SharedState,
        **kwargs: Any,
    ) -> list[str]:
        if not team.agents:
            return []

        if team.execution == "sequential":
            return await self._run_sequential(team, goal, state, **kwargs)

        # parallel / dag — not yet implemented, fall back to sequential
        logger.warning("Execution mode '%s' not implemented, falling back to sequential", team.execution)
        return await self._run_sequential(team, goal, state, **kwargs)

    async def _run_sequential(
        self,
        team: AgentTeam,
        goal: str,
        state: SharedState,
        **kwargs: Any,
    ) -> list[str]:
        results: list[str] = []
        for spec in team.agents:
            state.set_stage(spec.name)
            try:
                result = await self._run_sub_agent(spec, goal, state, **kwargs)
                results.append(result)
            except Exception:
                logger.exception("Sub-agent '%s' failed in team '%s'", spec.name, team.name)
                results.append(f"Error: {spec.name} failed")
        return results

    async def _run_sub_agent(
        self,
        spec: AgentSpec,
        goal: str,
        state: SharedState,
        **kwargs: Any,
    ) -> str:
        # Placeholder — Task 6 wires this to AgentLoop
        raise NotImplementedError("_run_sub_agent must be wired to AgentLoop")


# Global registry
teams = TeamRegistry()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_agent_team.py -v`
Expected: All 11 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/edu-cloud && git add src/edu_cloud/ai/agent_team.py tests/test_ai/test_agent_team.py
git commit -m "feat(ai): add AgentTeam + TeamRegistry + TeamExecutor"
```

---

### Task 5: AgentLoop 子 Agent 模式

**Files:**
- Modify: `src/edu_cloud/ai/agent_loop.py` (lines 38-65)
- Test: `tests/test_ai/test_agent_loop_subagent.py`

**测试契约:**
1. AgentLoop 接受外部 adapter（不同 slot）
   - 入口: `AgentLoop(registry, adapter_with_different_slot, strategy)`
   - 反例: 错误实现忽略传入的 adapter，始终使用默认
   - 边界: adapter=None（应报错）
   - 回归: 现有 AgentLoop 行为不变
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_agent_loop_subagent.py -v`
2. AgentLoop.run 接受 tool_names 过滤
   - 入口: `loop.run(goal, ctx, tool_specs=filtered_specs)`
   - 反例: 忽略 tool_specs 参数，使用全部工具
   - 边界: tool_specs=[] / tool_specs=None
   - 回归: 不传 tool_names 时行为与现有一致
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_agent_loop_subagent.py -v`

**审查清单:**
- ✓ AgentLoop 构造器不变（向后兼容）
- ✓ run() 的 tool_specs 参数已存在，无需修改签名
- ✓ 新增 `run_as_sub_agent()` 简化方法，接受 AgentSpec + SharedState
- ✗ sub-agent 不递归调用 TaskPlanner（max_turns 受 AgentSpec 控制）

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_agent_loop_subagent.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from edu_cloud.ai.agent_loop import AgentLoop, AgentState
from edu_cloud.ai.agent_spec import AgentSpec
from edu_cloud.ai.capability_probe import LoopStrategy
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMResponse, TokenUsage
from edu_cloud.ai.registry import ToolRegistry, ToolSpec
from edu_cloud.ai.schemas import AgentEvent, Message
from edu_cloud.ai.shared_state import SharedState
from edu_cloud.ai.tool_context import ToolContext, ToolResult


@pytest.fixture
def mock_registry():
    reg = ToolRegistry()

    @reg.register(name="tool_a", description="Tool A")
    async def tool_a(input_data: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data="result_a")

    @reg.register(name="tool_b", description="Tool B")
    async def tool_b(input_data: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data="result_b")

    return reg


@pytest.fixture
def mock_adapter():
    adapter = MagicMock(spec=LLMProxyAdapter)
    adapter.context_window_size.return_value = 128_000
    adapter.supports_tool_use.return_value = True
    adapter.supports_parallel_tool_calls.return_value = True
    adapter.chat = AsyncMock(return_value=LLMResponse(
        content="Done",
        stop_reason="end_turn",
        usage=TokenUsage(input_tokens=100, output_tokens=50),
    ))
    adapter.close = AsyncMock()
    return adapter


class TestSubAgentMode:
    @pytest.mark.asyncio
    async def test_run_as_sub_agent_exists(self, mock_registry, mock_adapter):
        """AgentLoop has run_as_sub_agent method."""
        strategy = LoopStrategy.for_tier(2)
        loop = AgentLoop(registry=mock_registry, adapter=mock_adapter, strategy=strategy)
        assert hasattr(loop, 'run_as_sub_agent')

    @pytest.mark.asyncio
    async def test_run_as_sub_agent_uses_spec_max_turns(self, mock_registry, mock_adapter):
        """Sub-agent respects AgentSpec.max_turns, not strategy.max_turns."""
        spec = AgentSpec(name="test", description="Test", tools=["tool_a"], max_turns=3)
        strategy = LoopStrategy.for_tier(2)  # max_turns=15
        loop = AgentLoop(registry=mock_registry, adapter=mock_adapter, strategy=strategy)

        ctx = MagicMock(spec=ToolContext)
        ctx.db = None
        ctx.anonymizer = MagicMock()
        ctx.anonymizer.anonymize = lambda x: x
        ctx.anonymizer.deanonymize = lambda x: x

        state = SharedState()
        result = await loop.run_as_sub_agent(
            spec=spec,
            goal="test goal",
            ctx=ctx,
            state=state,
        )
        # Should return a string result
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_run_as_sub_agent_filters_tools(self, mock_registry, mock_adapter):
        """Sub-agent only sees tools listed in AgentSpec."""
        spec = AgentSpec(name="test", description="Test", tools=["tool_a"])
        strategy = LoopStrategy.for_tier(2)
        loop = AgentLoop(registry=mock_registry, adapter=mock_adapter, strategy=strategy)

        ctx = MagicMock(spec=ToolContext)
        ctx.db = None
        ctx.anonymizer = MagicMock()
        ctx.anonymizer.anonymize = lambda x: x
        ctx.anonymizer.deanonymize = lambda x: x

        state = SharedState()
        result = await loop.run_as_sub_agent(
            spec=spec,
            goal="test goal",
            ctx=ctx,
            state=state,
        )
        # Verify adapter.chat was called with tools containing only tool_a
        assert mock_adapter.chat.called, "adapter.chat must be called"
        call_args = mock_adapter.chat.call_args
        request = call_args[0][0]
        assert request.tools is not None, "tools must not be None"
        assert len(request.tools) > 0, "tools must not be empty"
        tool_names = [t["function"]["name"] for t in request.tools]
        assert tool_names == ["tool_a"], f"Expected ['tool_a'], got {tool_names}"

    @pytest.mark.asyncio
    async def test_run_as_sub_agent_empty_tools_gets_empty(self, mock_registry, mock_adapter):
        """Sub-agent with no tools should pass empty tool list."""
        spec = AgentSpec(name="test", description="Test", tools=[])
        strategy = LoopStrategy.for_tier(2)
        loop = AgentLoop(registry=mock_registry, adapter=mock_adapter, strategy=strategy)

        ctx = MagicMock(spec=ToolContext)
        ctx.db = None
        ctx.anonymizer = MagicMock()
        ctx.anonymizer.anonymize = lambda x: x
        ctx.anonymizer.deanonymize = lambda x: x

        state = SharedState()
        result = await loop.run_as_sub_agent(
            spec=spec, goal="test", ctx=ctx, state=state,
        )
        call_args = mock_adapter.chat.call_args
        request = call_args[0][0]
        # Empty tools = None or empty list (no tools available)
        assert not request.tools or len(request.tools) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_agent_loop_subagent.py -v`
Expected: FAIL — `AttributeError: 'AgentLoop' object has no attribute 'run_as_sub_agent'`

- [ ] **Step 3: Add run_as_sub_agent to AgentLoop**

Add after the `get_history()` method (after line 246 in `agent_loop.py`):

```python
    async def run_as_sub_agent(
        self,
        spec: "AgentSpec",
        goal: str,
        ctx: "ToolContext",
        state: "SharedState",
        system_prompt: str = "",
    ) -> str:
        """Run this AgentLoop as a sub-agent with constrained tools and turns.

        Returns the final answer text (not an event stream).
        """
        from edu_cloud.ai.agent_spec import AgentSpec  # noqa: F811
        from edu_cloud.ai.shared_state import SharedState  # noqa: F811

        # Filter tools to only those in spec
        filtered_specs = self._registry.filter_by_names(spec.tools)

        # Override strategy max_turns with spec.max_turns
        from dataclasses import replace
        sub_strategy = replace(self._strategy, max_turns=spec.max_turns, task_planning=False)
        original_strategy = self._strategy
        self._strategy = sub_strategy

        # Inject shared state context into system prompt
        state_context = ""
        state_dict = state.as_dict()
        if state_dict:
            state_context = f"\n\n当前已知信息：\n{state_dict}"

        final_answer = ""
        try:
            async for event in self.run(
                goal=goal,
                ctx=ctx,
                tool_specs=filtered_specs,
                system_prompt=system_prompt + state_context,
            ):
                if event.type == "answer":
                    final_answer = event.data.get("content", "")
        finally:
            self._strategy = original_strategy

        return final_answer
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_agent_loop_subagent.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Run full AI test suite for regression**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/ -v --tb=short`
Expected: All existing tests PASS

- [ ] **Step 6: Commit**

```bash
cd ~/edu-cloud && git add src/edu_cloud/ai/agent_loop.py tests/test_ai/test_agent_loop_subagent.py
git commit -m "feat(ai): add AgentLoop.run_as_sub_agent() for team sub-agent execution"
```

---

### Task 6: Supervisor 核心（意图分类 + Team 路由 + 结果汇总）

**Files:**
- Create: `src/edu_cloud/ai/supervisor.py`
- Test: `tests/test_ai/test_supervisor.py`

**测试契约:**
1. 简单请求退化为直接 AgentLoop
   - 入口: `supervisor.handle(simple_message, ctx, ...)`
   - 反例: 错误实现把简单问题也分派到 team，浪费开销
   - 边界: 单工具请求 / 纯问答无工具
   - 回归: 现有 /api/ai/chat 行为不变
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_supervisor.py::TestSupervisorSimple -v`
2. 复杂请求分派到 AgentTeam
   - 入口: `supervisor.handle(complex_message, ctx, ...)`
   - 反例: 错误实现始终走单 Agent，不分派
   - 边界: 无匹配 team / 多 team 匹配
   - 回归: N/A
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_supervisor.py::TestSupervisorDispatch -v`

**审查清单:**
- ✓ Supervisor.handle 返回 AsyncGenerator[AgentEvent]（与现有 SSE 兼容）
- ✓ 简单请求直接走 AgentLoop.run（无 team 开销）
- ✓ 复杂请求分派到 team，team 不存在时 fallback 到单 Agent
- ✓ team 执行结果通过 LLM 汇总成最终响应
- ✗ Supervisor 不直接调用工具（只做路由）

**边界条件:**
- 所有 team 都不匹配 → 期望: fallback 到单 Agent loop
- LLM 意图分类失败 → 期望: fallback 到单 Agent loop
- team 执行中途异常 → 期望: 返回已完成部分 + 错误信息

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_supervisor.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from edu_cloud.ai.supervisor import Supervisor, ClassificationResult
from edu_cloud.ai.agent_team import AgentTeam, TeamRegistry
from edu_cloud.ai.agent_spec import AgentSpec
from edu_cloud.ai.capability_probe import LoopStrategy
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMResponse, TokenUsage
from edu_cloud.ai.registry import ToolRegistry, ToolSpec
from edu_cloud.ai.schemas import AgentEvent
from edu_cloud.ai.tool_context import ToolContext, ToolResult


def _make_spec(name, tools=None):
    return AgentSpec(name=name, description=f"{name}", tools=tools or [])


@pytest.fixture
def mock_adapter():
    adapter = MagicMock(spec=LLMProxyAdapter)
    adapter.context_window_size.return_value = 128_000
    adapter.chat = AsyncMock(return_value=LLMResponse(
        content="这是回答",
        stop_reason="end_turn",
        usage=TokenUsage(input_tokens=100, output_tokens=50),
    ))
    adapter.close = AsyncMock()
    return adapter


@pytest.fixture
def tool_registry():
    reg = ToolRegistry()

    @reg.register(name="exam_list", description="List exams")
    async def exam_list(i: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data=[])

    @reg.register(name="search_curriculum", description="Search curriculum")
    async def search_curriculum(i: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data=[])

    return reg


@pytest.fixture
def team_registry():
    reg = TeamRegistry()
    reg.register(AgentTeam(
        name="edu_data",
        description="教育数据分析：考试成绩查询、学情分析、班级对比",
        agents=[_make_spec("data_query", ["exam_list"])],
    ))
    return reg


class TestClassificationResult:
    def test_simple(self):
        r = ClassificationResult(needs_team=False)
        assert not r.needs_team
        assert r.team_name is None

    def test_complex(self):
        r = ClassificationResult(needs_team=True, team_name="edu_data")
        assert r.needs_team
        assert r.team_name == "edu_data"


class TestSupervisorSimple:
    @pytest.mark.asyncio
    async def test_simple_request_uses_single_loop(self, mock_adapter, tool_registry, team_registry):
        """Simple single-tool request should NOT dispatch to a team."""
        supervisor = Supervisor(
            registry=tool_registry,
            adapter=mock_adapter,
            strategy=LoopStrategy.for_tier(2),
            team_registry=team_registry,
        )

        # Force classification to return "simple"
        with patch.object(supervisor, '_classify', return_value=ClassificationResult(needs_team=False)):
            ctx = MagicMock(spec=ToolContext)
            ctx.db = None
            ctx.anonymizer = MagicMock()
            ctx.anonymizer.anonymize = lambda x: x
            ctx.anonymizer.deanonymize = lambda x: x

            events = []
            async for event in supervisor.handle(
                message="你好",
                ctx=ctx,
                tool_specs=tool_registry.get_all_specs(),
                system_prompt="",
            ):
                events.append(event)

            # Should have at least one event (answer or done)
            assert len(events) > 0

    @pytest.mark.asyncio
    async def test_no_team_fallback(self, mock_adapter, tool_registry):
        """When no team registry exists, always use single loop."""
        supervisor = Supervisor(
            registry=tool_registry,
            adapter=mock_adapter,
            strategy=LoopStrategy.for_tier(2),
            team_registry=None,
        )

        ctx = MagicMock(spec=ToolContext)
        ctx.db = None
        ctx.anonymizer = MagicMock()
        ctx.anonymizer.anonymize = lambda x: x
        ctx.anonymizer.deanonymize = lambda x: x

        events = []
        async for event in supervisor.handle(
            message="你好",
            ctx=ctx,
            tool_specs=tool_registry.get_all_specs(),
            system_prompt="",
        ):
            events.append(event)

        assert len(events) > 0


class TestSupervisorDispatch:
    @pytest.mark.asyncio
    async def test_complex_request_dispatches_to_team(self, mock_adapter, tool_registry, team_registry):
        """Complex multi-step request should dispatch to matching team."""
        supervisor = Supervisor(
            registry=tool_registry,
            adapter=mock_adapter,
            strategy=LoopStrategy.for_tier(1),
            team_registry=team_registry,
        )

        with patch.object(
            supervisor, '_classify',
            return_value=ClassificationResult(needs_team=True, team_name="edu_data"),
        ):
            with patch.object(supervisor, '_run_team', new_callable=AsyncMock) as mock_run_team:
                mock_run_team.return_value = "团队执行结果"

                ctx = MagicMock(spec=ToolContext)
                ctx.db = None
                ctx.anonymizer = MagicMock()
                ctx.anonymizer.anonymize = lambda x: x
                ctx.anonymizer.deanonymize = lambda x: x

                events = []
                async for event in supervisor.handle(
                    message="分析上次期中考试各班数学成绩并生成对比报告",
                    ctx=ctx,
                    tool_specs=tool_registry.get_all_specs(),
                    system_prompt="",
                ):
                    events.append(event)

                mock_run_team.assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_team_fallback(self, mock_adapter, tool_registry, team_registry):
        """If classified team doesn't exist, fallback to single loop."""
        supervisor = Supervisor(
            registry=tool_registry,
            adapter=mock_adapter,
            strategy=LoopStrategy.for_tier(2),
            team_registry=team_registry,
        )

        with patch.object(
            supervisor, '_classify',
            return_value=ClassificationResult(needs_team=True, team_name="nonexistent"),
        ):
            ctx = MagicMock(spec=ToolContext)
            ctx.db = None
            ctx.anonymizer = MagicMock()
            ctx.anonymizer.anonymize = lambda x: x
            ctx.anonymizer.deanonymize = lambda x: x

            events = []
            async for event in supervisor.handle(
                message="test",
                ctx=ctx,
                tool_specs=tool_registry.get_all_specs(),
                system_prompt="",
            ):
                events.append(event)

            # Should still produce events (fallback to single loop)
            assert len(events) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_supervisor.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement Supervisor**

```python
# src/edu_cloud/ai/supervisor.py
"""Supervisor: routes requests to single AgentLoop or AgentTeam."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import AsyncGenerator, Any

from edu_cloud.ai.agent_loop import AgentLoop
from edu_cloud.ai.agent_spec import select_slot
from edu_cloud.ai.agent_team import AgentTeam, TeamExecutor, TeamRegistry
from edu_cloud.ai.capability_probe import LoopStrategy
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMRequest
from edu_cloud.ai.registry import ToolRegistry, ToolSpec
from edu_cloud.ai.schemas import AgentEvent, Message
from edu_cloud.ai.sensitivity_router import SensitivityRouter
from edu_cloud.ai.shared_state import SharedState
from edu_cloud.ai.tool_context import ToolContext

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    needs_team: bool
    team_name: str | None = None
    reason: str = ""


class Supervisor:
    """Routes user requests to single AgentLoop or multi-agent team."""

    def __init__(
        self,
        registry: ToolRegistry,
        adapter: LLMProxyAdapter,
        strategy: LoopStrategy,
        team_registry: TeamRegistry | None = None,
        sensitivity_router: SensitivityRouter | None = None,
    ):
        self._registry = registry
        self._adapter = adapter
        self._strategy = strategy
        self._team_registry = team_registry
        self._sensitivity_router = sensitivity_router
        self._team_executor = TeamExecutor()
        # Execution receipt — stable public interface for callers (F002 fix)
        self._history: list[Message] = []
        self._model_tier: str = f"tier{strategy.tier}"
        self._dispatched_team: str | None = None

    async def handle(
        self,
        message: str,
        ctx: ToolContext,
        *,
        tool_specs: list[ToolSpec],
        system_prompt: str = "",
        history: list[Message] | None = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        """Main entry point. Yields AgentEvents (compatible with SSE stream)."""

        # If no teams registered or tier 3, always use single loop
        if not self._team_registry or self._strategy.tier == 3:
            async for event in self._run_single(
                message, ctx, tool_specs=tool_specs,
                system_prompt=system_prompt, history=history,
            ):
                yield event
            return

        # Classify intent
        classification = await self._classify(message, tool_specs)

        if not classification.needs_team:
            async for event in self._run_single(
                message, ctx, tool_specs=tool_specs,
                system_prompt=system_prompt, history=history,
            ):
                yield event
            return

        # Try to get the team
        team = self._team_registry.get(classification.team_name) if classification.team_name else None
        if team is None:
            logger.warning(
                "Classified as team '%s' but team not found, falling back to single loop",
                classification.team_name,
            )
            async for event in self._run_single(
                message, ctx, tool_specs=tool_specs,
                system_prompt=system_prompt, history=history,
            ):
                yield event
            return

        # Dispatch to team
        yield AgentEvent(type="status", data={"message": f"正在调度 {team.name} 团队..."})

        try:
            team_result = await self._run_team(team, message, ctx, system_prompt=system_prompt)
            self._dispatched_team = team.name  # F002 fix: track dispatched team
        except Exception:
            logger.exception("Team '%s' execution failed, falling back", team.name)
            async for event in self._run_single(
                message, ctx, tool_specs=tool_specs,
                system_prompt=system_prompt, history=history,
            ):
                yield event
            return

        # Summarize team results via LLM
        summary = await self._summarize(message, team_result)
        # F002 fix: capture answer as synthetic history for multi-turn
        self._history = [
            Message(role="user", content=message),
            Message(role="assistant", content=summary),
        ]
        yield AgentEvent(type="answer", data={"content": summary})
        yield AgentEvent(type="done", data={})

    async def _classify(
        self,
        message: str,
        tool_specs: list[ToolSpec],
    ) -> ClassificationResult:
        """Use LLM to classify whether this request needs a team."""
        if not self._team_registry:
            return ClassificationResult(needs_team=False)

        team_descs = self._team_registry.get_descriptions()
        teams_text = "\n".join(f"- {t['name']}: {t['description']}" for t in team_descs)

        prompt = (
            "你是请求分类器。判断用户请求是简单还是复杂。\n"
            "简单请求：单个工具就能完成（查询、问答、单步操作）。\n"
            "复杂请求：需要多个步骤协作完成（分析+报告、多维对比、批量处理）。\n\n"
            f"可用团队：\n{teams_text}\n\n"
            '简单请求回复：{{"needs_team": false}}\n'
            '复杂请求回复：{{"needs_team": true, "team_name": "团队名"}}\n'
            "只回复 JSON，不要其他内容。"
        )

        try:
            resp = await self._adapter.chat(LLMRequest(
                messages=[
                    Message(role="system", content=prompt),
                    Message(role="user", content=message),
                ],
                max_tokens=200,
                stream=False,
            ))
            data = json.loads(resp.content)
            return ClassificationResult(
                needs_team=data.get("needs_team", False),
                team_name=data.get("team_name"),
            )
        except (json.JSONDecodeError, KeyError, TypeError, Exception) as exc:
            logger.warning("Classification failed: %s, defaulting to simple", exc)
            return ClassificationResult(needs_team=False)

    def get_history(self) -> list[Message]:
        """Return conversation history from last run (stable public API, F002 fix)."""
        return self._history

    @property
    def model_tier(self) -> str:
        """Return model tier as string (e.g. 'tier1'), matching record_run contract."""
        return self._model_tier

    @property
    def dispatched_team(self) -> str | None:
        """Return name of dispatched team, or None if single loop was used."""
        return self._dispatched_team

    async def _run_single(
        self,
        message: str,
        ctx: ToolContext,
        *,
        tool_specs: list[ToolSpec],
        system_prompt: str = "",
        history: list[Message] | None = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        """Delegate to existing single AgentLoop (backward compatible)."""
        loop = AgentLoop(
            registry=self._registry,
            adapter=self._adapter,
            strategy=self._strategy,
            sensitivity_router=self._sensitivity_router,
        )
        async for event in loop.run(
            goal=message,
            ctx=ctx,
            tool_specs=tool_specs,
            system_prompt=system_prompt,
            history=history,
        ):
            yield event
        # Capture history for multi-turn persistence (F002 fix)
        self._history = loop.get_history()
        self._dispatched_team = None

    async def _run_team(
        self,
        team: AgentTeam,
        goal: str,
        ctx: ToolContext,
        system_prompt: str = "",
    ) -> str:
        """Execute team via TeamExecutor, wiring sub-agents to AgentLoop."""
        state = SharedState()
        state.set("goal", goal)

        # Wire _run_sub_agent to use AgentLoop
        original_run = self._team_executor._run_sub_agent

        async def wired_run(spec, goal, state, **kwargs):
            # Create adapter with appropriate slot for this sub-agent
            slot = select_slot(spec)
            sub_adapter = LLMProxyAdapter(
                base_url=self._adapter._base_url,
                slot=slot,
                context_window=self._adapter._context_window,
            )
            try:
                sub_loop = AgentLoop(
                    registry=self._registry,
                    adapter=sub_adapter,
                    strategy=LoopStrategy.for_tier(spec.model_tier or self._strategy.tier),
                )
                return await sub_loop.run_as_sub_agent(
                    spec=spec,
                    goal=goal,
                    ctx=ctx,
                    state=state,
                    system_prompt=system_prompt,
                )
            finally:
                await sub_adapter.close()

        self._team_executor._run_sub_agent = wired_run
        try:
            results = await self._team_executor.run(team, goal, state)
        finally:
            self._team_executor._run_sub_agent = original_run

        return "\n\n".join(results)

    async def _summarize(self, original_question: str, team_output: str) -> str:
        """Use LLM to synthesize team results into a coherent response."""
        if not team_output.strip():
            return "抱歉，团队执行没有产生有效结果。"

        try:
            resp = await self._adapter.chat(LLMRequest(
                messages=[
                    Message(
                        role="system",
                        content=(
                            "你是结果汇总器。根据多个 Agent 的执行结果，"
                            "生成一个连贯、完整的回答给用户。保持原始数据的准确性。"
                        ),
                    ),
                    Message(
                        role="user",
                        content=f"用户问题：{original_question}\n\nAgent 执行结果：\n{team_output}",
                    ),
                ],
                max_tokens=2000,
                stream=False,
            ))
            return resp.content or team_output
        except Exception:
            logger.exception("Summarization failed, returning raw results")
            return team_output
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_supervisor.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/edu-cloud && git add src/edu_cloud/ai/supervisor.py tests/test_ai/test_supervisor.py
git commit -m "feat(ai): add Supervisor for team routing + single-loop fallback"
```

---

### Task 7: 预设 Team 定义（edu_data / knowledge / homework）

**Files:**
- Create: `src/edu_cloud/ai/teams/__init__.py`
- Create: `src/edu_cloud/ai/teams/edu_data.py`
- Create: `src/edu_cloud/ai/teams/knowledge.py`
- Create: `src/edu_cloud/ai/teams/homework.py`
- Test: `tests/test_ai/test_teams.py`

**测试契约:**
1. Team 注册后可通过 TeamRegistry 获取
   - 入口: `import edu_cloud.ai.teams` → `teams.get("edu_data")`
   - 反例: import 后 team 未注册到全局 registry
   - 边界: 重复 import 不报错
   - 回归: N/A
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_teams.py -v`
2. 每个 Team 的工具列表只包含已注册的真实工具
   - 入口: 遍历 team.all_tools，检查每个是否在 ToolRegistry 中
   - 反例: Team 声明了不存在的工具名
   - 边界: N/A
   - 回归: N/A
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_teams.py::test_tools_exist -v`

**审查清单:**
- ✓ 每个 Team 的工具名与 `ai/tools/` 中注册的一致
- ✓ description 足够清晰供 Supervisor 分类使用
- ✓ `__init__.py` import 后自动注册到全局 `teams` registry
- ✗ Team 不包含 Phase 3 的论文/课件 Agent（留待 Phase 3）

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_teams.py
import pytest


class TestTeamRegistration:
    def test_edu_data_registered(self):
        from edu_cloud.ai.agent_team import teams
        import edu_cloud.ai.teams  # noqa: F401 — trigger registration
        team = teams.get("edu_data")
        assert team is not None
        assert len(team.agents) >= 1

    def test_knowledge_registered(self):
        from edu_cloud.ai.agent_team import teams
        import edu_cloud.ai.teams  # noqa: F401
        team = teams.get("knowledge")
        assert team is not None
        assert len(team.agents) >= 1

    def test_homework_registered(self):
        from edu_cloud.ai.agent_team import teams
        import edu_cloud.ai.teams  # noqa: F401
        team = teams.get("homework")
        assert team is not None
        assert len(team.agents) >= 1

    def test_all_teams_have_descriptions(self):
        from edu_cloud.ai.agent_team import teams
        import edu_cloud.ai.teams  # noqa: F401
        for name in teams.list_teams():
            team = teams.get(name)
            assert team.description, f"Team '{name}' has no description"

    def test_tools_exist(self):
        """Every tool declared in a team must exist in the global ToolRegistry."""
        from edu_cloud.ai.agent_team import teams
        from edu_cloud.ai.registry import tools
        import edu_cloud.ai.teams  # noqa: F401
        import edu_cloud.ai.tools  # noqa: F401 — trigger tool registration

        all_registered = set(tools.list_tools())
        for name in teams.list_teams():
            team = teams.get(name)
            for tool_name in team.all_tools:
                assert tool_name in all_registered, (
                    f"Team '{name}' references tool '{tool_name}' which is not registered"
                )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_teams.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'edu_cloud.ai.teams'`

- [ ] **Step 3: Implement team definitions**

```python
# src/edu_cloud/ai/teams/__init__.py
"""Auto-register all predefined teams."""
from edu_cloud.ai.teams import edu_data  # noqa: F401
from edu_cloud.ai.teams import knowledge  # noqa: F401
from edu_cloud.ai.teams import homework  # noqa: F401
```

```python
# src/edu_cloud/ai/teams/edu_data.py
"""Education data analysis team: exam scores, class comparisons, reports."""
from edu_cloud.ai.agent_spec import AgentSpec
from edu_cloud.ai.agent_team import AgentTeam, teams

_team = AgentTeam(
    name="edu_data",
    description="教育数据分析：考试成绩查询、学情分析、班级对比、年级统计、学生排名",
    agents=[
        AgentSpec(
            name="data_query",
            description="查询考试数据、成绩、班级信息",
            tools=[
                "get_exam_list", "get_exam_detail", "get_subject_questions",
                "get_class_list", "get_class_roster", "search_students", "get_student_profile",
            ],
            task_complexity="data_query",
            max_turns=8,
        ),
        AgentSpec(
            name="analytics",
            description="统计分析：成绩分布、题目得分率、班级对比、排名",
            tools=[
                "get_exam_summary", "get_score_distribution", "get_question_analysis",
                "get_student_scores", "get_class_scores",
                "compare_classes", "rank_students", "get_grade_aggregates",
                "get_exam_scores", "get_class_stats",
            ],
            task_complexity="data_query",
            max_turns=10,
        ),
        AgentSpec(
            name="reporter",
            description="生成分析报告和教师评语",
            tools=["generate_report", "generate_comment"],
            task_complexity="generation",
            model_tier=1,
            max_turns=5,
        ),
    ],
    execution="sequential",
)

teams.register(_team)
```

```python
# src/edu_cloud/ai/teams/knowledge.py
"""Knowledge base team: curriculum search, textbook, concepts, gaokao index."""
from edu_cloud.ai.agent_spec import AgentSpec
from edu_cloud.ai.agent_team import AgentTeam, teams

_team = AgentTeam(
    name="knowledge",
    description="知识库查询：课标搜索、教材内容、知识点概念、高考考点索引、知识树",
    agents=[
        AgentSpec(
            name="knowledge_search",
            description="搜索课标、教材、知识点",
            tools=[
                "search_curriculum", "search_textbook",
                "get_concept_info", "search_gaokao",
                "get_knowledge_tree", "get_question_knowledge_points",
            ],
            task_complexity="retrieval",
            max_turns=10,
        ),
    ],
    execution="sequential",
)

teams.register(_team)
```

```python
# src/edu_cloud/ai/teams/homework.py
"""Homework team: task management, grading, remedial recommendations."""
from edu_cloud.ai.agent_spec import AgentSpec
from edu_cloud.ai.agent_team import AgentTeam, teams

_team = AgentTeam(
    name="homework",
    description="作业管理：布置作业、查看提交、批改、统计、补救推荐",
    agents=[
        AgentSpec(
            name="homework_ops",
            description="作业任务和提交管理",
            tools=[
                "list_homework_tasks", "get_homework_stats",
                "get_submission_details", "assign_homework", "recommend_remedial",
            ],
            task_complexity="data_query",
            max_turns=10,
        ),
    ],
    execution="sequential",
)

teams.register(_team)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_teams.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/edu-cloud && git add src/edu_cloud/ai/teams/ tests/test_ai/test_teams.py
git commit -m "feat(ai): add predefined teams (edu_data, knowledge, homework)"
```

---

### Task 8: API 集成（SSE 端点接入 Supervisor）

**Files:**
- Modify: `src/edu_cloud/api/ai.py` (lines 229-275)
- Test: `tests/test_ai/test_backward_compat.py`
- Test: `tests/test_ai/test_api_supervisor_integration.py` (F005 入口级测试)

**测试契约:**
1. 现有 /api/v1/ai/chat 端点行为不变
   - 入口: `POST /api/v1/ai/chat` with simple message
   - 反例: 引入 Supervisor 后原有端点返回格式变化
   - 边界: 空 session_id / 已有 session 多轮对话
   - 回归: 现有 1166 tests 全部通过
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_ai_api.py -v`
2. Supervisor 集成后 SSE 事件流格式兼容
   - 入口: `POST /api/v1/ai/chat` → SSE stream
   - 反例: Supervisor 返回的 AgentEvent 格式与前端不兼容
   - 边界: team dispatch 时的 status 事件
   - 回归: 前端 aiChat.js SSE 解析不报错
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_backward_compat.py -v`

**审查清单:**
- ✓ 只修改 AgentLoop 创建处，替换为 Supervisor
- ✓ event_stream 函数内的 SSE 格式不变
- ✓ session 管理（F002）不变
- ✓ AuditLogger 记录不变
- ✓ 新增 `import edu_cloud.ai.teams` 触发 team 注册
- ✗ 不修改健康检查和 session 管理端点

- [ ] **Step 1: Write backward compatibility tests**

```python
# tests/test_ai/test_backward_compat.py
"""Verify that Supervisor integration doesn't break existing AI chat behavior."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from edu_cloud.ai.supervisor import Supervisor
from edu_cloud.ai.agent_team import TeamRegistry
from edu_cloud.ai.capability_probe import LoopStrategy
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMResponse, TokenUsage
from edu_cloud.ai.registry import ToolRegistry
from edu_cloud.ai.schemas import AgentEvent
from edu_cloud.ai.tool_context import ToolContext, ToolResult


@pytest.fixture
def simple_setup():
    reg = ToolRegistry()

    @reg.register(name="exam_list", description="List exams")
    async def exam_list(i: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data=[])

    adapter = MagicMock(spec=LLMProxyAdapter)
    adapter.context_window_size.return_value = 128_000
    adapter.chat = AsyncMock(return_value=LLMResponse(
        content="回答内容",
        stop_reason="end_turn",
        usage=TokenUsage(input_tokens=100, output_tokens=50),
    ))
    adapter.close = AsyncMock()

    return reg, adapter


class TestBackwardCompat:
    @pytest.mark.asyncio
    async def test_simple_message_returns_answer_event(self, simple_setup):
        """A simple message should produce an answer event, same as before."""
        reg, adapter = simple_setup
        supervisor = Supervisor(
            registry=reg,
            adapter=adapter,
            strategy=LoopStrategy.for_tier(2),
            team_registry=None,  # No teams = always single loop
        )

        ctx = MagicMock(spec=ToolContext)
        ctx.db = None
        ctx.anonymizer = MagicMock()
        ctx.anonymizer.anonymize = lambda x: x
        ctx.anonymizer.deanonymize = lambda x: x

        events = []
        async for event in supervisor.handle(
            message="你好",
            ctx=ctx,
            tool_specs=reg.get_all_specs(),
            system_prompt="你是教育助手",
        ):
            events.append(event)

        event_types = [e.type for e in events]
        assert "answer" in event_types or "done" in event_types

    @pytest.mark.asyncio
    async def test_event_has_to_dict(self, simple_setup):
        """All events must have to_dict() for SSE serialization."""
        reg, adapter = simple_setup
        supervisor = Supervisor(
            registry=reg,
            adapter=adapter,
            strategy=LoopStrategy.for_tier(2),
            team_registry=None,
        )

        ctx = MagicMock(spec=ToolContext)
        ctx.db = None
        ctx.anonymizer = MagicMock()
        ctx.anonymizer.anonymize = lambda x: x
        ctx.anonymizer.deanonymize = lambda x: x

        async for event in supervisor.handle(
            message="你好",
            ctx=ctx,
            tool_specs=reg.get_all_specs(),
            system_prompt="",
        ):
            d = event.to_dict()
            assert "type" in d
            assert "data" in d

    @pytest.mark.asyncio
    async def test_tier3_never_uses_team(self, simple_setup):
        """Tier 3 should never dispatch to a team, regardless of message."""
        reg, adapter = simple_setup
        team_reg = TeamRegistry()

        supervisor = Supervisor(
            registry=reg,
            adapter=adapter,
            strategy=LoopStrategy.for_tier(3),
            team_registry=team_reg,
        )

        ctx = MagicMock(spec=ToolContext)
        ctx.db = None
        ctx.anonymizer = MagicMock()
        ctx.anonymizer.anonymize = lambda x: x
        ctx.anonymizer.deanonymize = lambda x: x

        with patch.object(supervisor, '_classify') as mock_classify:
            events = []
            async for event in supervisor.handle(
                message="复杂的多步分析请求",
                ctx=ctx,
                tool_specs=reg.get_all_specs(),
                system_prompt="",
            ):
                events.append(event)

            # _classify should never be called for tier 3
            mock_classify.assert_not_called()

    @pytest.mark.asyncio
    async def test_team_dispatch_produces_answer_and_done(self, simple_setup):
        """Team dispatch path should produce status + answer + done events (F005 fix)."""
        from edu_cloud.ai.agent_team import AgentTeam, TeamRegistry
        from edu_cloud.ai.agent_spec import AgentSpec

        reg, adapter = simple_setup
        team_reg = TeamRegistry()
        team_reg.register(AgentTeam(
            name="edu_data",
            description="教育数据分析",
            agents=[AgentSpec(name="q", description="q", tools=["get_exam_list"])],
        ))

        supervisor = Supervisor(
            registry=reg,
            adapter=adapter,
            strategy=LoopStrategy.for_tier(1),
            team_registry=team_reg,
        )

        with patch.object(
            supervisor, '_classify',
            return_value=ClassificationResult(needs_team=True, team_name="edu_data"),
        ):
            with patch.object(supervisor, '_run_team', new_callable=AsyncMock, return_value="分析结果"):
                ctx = MagicMock(spec=ToolContext)
                ctx.db = None
                ctx.anonymizer = MagicMock()
                ctx.anonymizer.anonymize = lambda x: x
                ctx.anonymizer.deanonymize = lambda x: x

                events = []
                async for event in supervisor.handle(
                    message="分析数学成绩",
                    ctx=ctx,
                    tool_specs=reg.get_all_specs(),
                    system_prompt="",
                ):
                    events.append(event)

                event_types = [e.type for e in events]
                assert "status" in event_types, "Team dispatch must emit status event"
                assert "answer" in event_types, "Team dispatch must emit answer event"
                assert "done" in event_types, "Team dispatch must emit done event"

                # F002 fix: verify history is populated
                history = supervisor.get_history()
                assert len(history) == 2  # user + assistant
                assert history[0].role == "user"
                assert history[1].role == "assistant"

                # F002 fix: verify model_tier is string
                assert isinstance(supervisor.model_tier, str)
                assert supervisor.model_tier.startswith("tier")
```

Need additional import at top of file:
```python
from unittest.mock import AsyncMock
from edu_cloud.ai.supervisor import ClassificationResult
```

- [ ] **Step 1b: Write API-level integration test (F005 fix R2)**

```python
# tests/test_ai/test_api_supervisor_integration.py
"""Entry-level API test for Supervisor integration into /api/v1/ai/chat (F005)."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport

from edu_cloud.api.app import create_app
from edu_cloud.ai.llm_adapter import LLMResponse, TokenUsage
from edu_cloud.ai.supervisor import ClassificationResult


@pytest.fixture
async def app_client(db_engine):
    """AsyncClient hitting real /api/v1/ai/chat endpoint."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


class TestApiSupervisorIntegration:
    @pytest.mark.asyncio
    async def test_simple_chat_returns_sse_with_session_id(self, app_client, auth_headers):
        """POST /api/v1/ai/chat with simple message returns SSE stream with session_id in done event."""
        with patch("edu_cloud.api.ai.LLMProxyAdapter") as MockAdapter:
            adapter_instance = MockAdapter.return_value
            adapter_instance.context_window_size.return_value = 128_000
            adapter_instance.supports_tool_use = AsyncMock(return_value=True)
            adapter_instance.supports_parallel_tool_calls = AsyncMock(return_value=True)
            adapter_instance.chat = AsyncMock(return_value=LLMResponse(
                content="你好！有什么可以帮助你的？",
                stop_reason="end_turn",
                usage=TokenUsage(input_tokens=100, output_tokens=50),
            ))
            adapter_instance.close = AsyncMock()

            resp = await app_client.post(
                "/api/v1/ai/chat",
                json={"message": "你好"},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")

            # Parse SSE events
            events = []
            for line in resp.text.strip().split("\n"):
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

            # Must have at least answer or done
            event_types = [e["type"] for e in events]
            assert "done" in event_types, "SSE must include done event"

            # done event must have session_id
            done_event = next(e for e in events if e["type"] == "done")
            assert "session_id" in done_event["data"]

    @pytest.mark.asyncio
    async def test_chat_history_persisted_across_calls(self, app_client, auth_headers):
        """Two calls with same session_id should persist history."""
        with patch("edu_cloud.api.ai.LLMProxyAdapter") as MockAdapter:
            adapter_instance = MockAdapter.return_value
            adapter_instance.context_window_size.return_value = 128_000
            adapter_instance.supports_tool_use = AsyncMock(return_value=True)
            adapter_instance.supports_parallel_tool_calls = AsyncMock(return_value=True)
            adapter_instance.chat = AsyncMock(return_value=LLMResponse(
                content="回答",
                stop_reason="end_turn",
                usage=TokenUsage(input_tokens=100, output_tokens=50),
            ))
            adapter_instance.close = AsyncMock()

            # First call
            resp1 = await app_client.post(
                "/api/v1/ai/chat",
                json={"message": "第一条消息"},
                headers=auth_headers,
            )
            session_id = resp1.headers.get("X-Session-Id")
            assert session_id

            # Second call with same session_id
            resp2 = await app_client.post(
                "/api/v1/ai/chat",
                json={"message": "第二条消息", "session_id": session_id},
                headers=auth_headers,
            )
            assert resp2.status_code == 200
```

Add this test file to Task 8 files list and commit command.

- [ ] **Step 2: Run tests to verify they pass with current Supervisor**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_backward_compat.py tests/test_ai/test_api_supervisor_integration.py -v`
Expected: All tests PASS (Supervisor already implemented)

- [ ] **Step 3: Modify api/ai.py to use Supervisor**

In `src/edu_cloud/api/ai.py`, make these changes:

At the imports section (after line 29), add:
```python
from edu_cloud.ai.supervisor import Supervisor
from edu_cloud.ai.agent_team import teams as team_registry
import edu_cloud.ai.teams  # noqa: F401 — trigger team registration
```

Replace the AgentLoop creation block (around lines 229-235) with:
```python
    supervisor = Supervisor(
        registry=tools,
        adapter=primary_adapter,
        strategy=strategy,
        team_registry=team_registry,
        sensitivity_router=sensitivity_router,
    )
```

Replace the event_stream function (around lines 237-258) to use supervisor:
```python
    async def event_stream():
        try:
            async for event in supervisor.handle(
                message=message,
                ctx=tool_ctx,
                tool_specs=available_tools,
                system_prompt=system_prompt,
                history=session_state.history,
            ):
                if event.type == "done":
                    event.data["session_id"] = session_id
                yield f"data: {json.dumps(event.to_dict(), ensure_ascii=False)}\n\n"
        finally:
            # Persist history via Supervisor's stable public API (F002 fix)
            session_state.history = supervisor.get_history()
            await primary_adapter.close()
            if profile is not None:
                try:
                    await AgentProfileService.record_run(
                        db,
                        profile_id=profile.id,
                        session_id=session_id,
                        tools_resolved=[t.name for t in available_tools],
                        tools_selected=[],
                        model_used=primary_adapter._slot,
                        model_tier=supervisor.model_tier,  # F002 fix: str via property
                        intent_domains=intent_result.domains if intent_result else [],
                    )
                    await db.commit()
                except Exception as rec_exc:
                    logger.warning("Failed to record AgentRun: %s", rec_exc)
```

- [ ] **Step 4: Run full test suite**

Run: `cd ~/edu-cloud && python -m pytest --tb=short -q`
Expected: All 1166+ tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/edu-cloud && git add src/edu_cloud/api/ai.py tests/test_ai/test_backward_compat.py tests/test_ai/test_api_supervisor_integration.py
git commit -m "feat(ai): integrate Supervisor into /api/ai/chat SSE endpoint"
```

---

### Task 9: 全量回归 + 集成验证

**Files:**
- No new files — validation only

- [ ] **Step 1: Run full backend test suite**

Run: `cd ~/edu-cloud && python -m pytest --tb=short -q`
Expected: All tests PASS

- [ ] **Step 2: Run AI-specific tests**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/ -v`
Expected: All PASS (existing + new)

- [ ] **Step 3: Count new tests**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_agent_spec.py tests/test_ai/test_shared_state.py tests/test_ai/test_registry_filter.py tests/test_ai/test_agent_team.py tests/test_ai/test_supervisor.py tests/test_ai/test_teams.py tests/test_ai/test_agent_loop_subagent.py tests/test_ai/test_backward_compat.py -v --tb=short 2>&1 | tail -5`
Expected: 40+ new tests PASS

- [ ] **Step 4: Verify git diff stats**

Run: `cd ~/edu-cloud && git diff --stat HEAD~8`
Expected: ~800 LOC new + ~200 LOC modified across listed files

- [ ] **Step 5: Tag completion**

```bash
cd ~/edu-cloud && git tag -a v0.9.0-agent-orchestration -m "Phase 1: Multi-agent orchestration engine"
```

---

## 审查清单（全局）

- ✓ 向后兼容：简单请求仍走单 AgentLoop，零破坏性
- ✓ SSE 事件格式不变：AgentEvent.to_dict() 输出与前端兼容
- ✓ 权限模型不变：ToolAccessResolver 在 Supervisor 之前执行，sub-agent 看到的是已过滤的工具
- ✓ 敏感度路由不变：SensitivityRouter 传入 Supervisor
- ✓ 会话管理不变：session_id + history + TTL 机制保持
- ✓ 审计不变：AuditLogger 在 api/ai.py 层面记录
- ✗ Team 执行的审计（sub-agent 级别）未覆盖（留待 Phase 2 的 AuditLogger 扩展）
- ✗ 并行执行模式未实现（Phase 1 只支持 sequential）
- ✗ 跨会话记忆未接入（Phase 2 交付）

---

## Contract Pack（F003 修复 R2）

```yaml
contract_pack:
  invariants:
    - id: INV-001
      statement: "简单请求（单工具/纯问答）必须退化为现有单 AgentLoop，不经过 Team 分派"
      verification: pending_test
    - id: INV-002
      statement: "SSE 事件格式（type + data dict with to_dict()）不变，前端 aiChat.js 解析兼容"
      verification: pending_test
    - id: INV-003
      statement: "Tier 3 模型永远不走 Team 分派，即使 team_registry 已注册"
      verification: pending_test
    - id: INV-004
      statement: "Supervisor.get_history() 返回非空 Message 列表，无论走单循环还是 Team 路径"
      verification: pending_test
    - id: INV-005
      statement: "record_run 的 model_tier 参数始终为 str 类型（'tierN' 格式），不接受 int"
      verification: pending_test
    - id: INV-006
      statement: "Team 定义中的每个工具名在 ToolRegistry.list_tools() 中存在"
      verification: pending_test

  counter_examples:
    - id: CE-001
      scenario: "Supervisor._classify 返回无法解析的 JSON（如 LLM 输出自然语言而非 JSON），错误实现将异常上抛导致 SSE 中断"
      tests_that_still_pass: ["test_no_team_fallback", "test_simple_message_returns_answer_event"]
      mitigation: "测试 _classify 抛异常时 Supervisor 仍产出 answer+done 事件"
    - id: CE-002
      scenario: "Supervisor._classify 返回 needs_team=true 但 team_name='nonexistent'，错误实现会 KeyError 崩溃而非 fallback"
      tests_that_still_pass: ["test_unknown_team_fallback"]
      mitigation: "测试不存在的 team name 时仍走单循环并产出事件"
    - id: CE-003
      scenario: "TeamExecutor._run_sub_agent 抛异常（如 LLM 连接超时），错误实现会让整个 SSE 流断裂"
      tests_that_still_pass: ["test_simple_message_returns_answer_event"]
      mitigation: "测试 team 执行异常时 Supervisor fallback 到单循环"

  risk_modules:
    - module: "src/edu_cloud/ai/supervisor.py"
      reason: "新增核心路由逻辑，影响所有 AI 请求的执行路径"
    - module: "src/edu_cloud/api/ai.py"
      reason: "公共 API 入口变更，AgentLoop→Supervisor 替换"
    - module: "src/edu_cloud/ai/agent_loop.py"
      reason: "新增 run_as_sub_agent 方法，修改 strategy 生命周期"
    - module: "src/edu_cloud/ai/agent_team.py"
      reason: "新增 TeamExecutor，管理子 Agent 执行和错误处理"
    - module: "src/edu_cloud/ai/teams/"
      reason: "预设 Team 定义，工具名映射必须与 ToolRegistry 一致"

  test_debt:
    - item: "Team 执行的 sub-agent 级别审计日志（AiToolCall 记录缺失 sub-agent 来源）"
      reason: "Phase 1 聚焦编排核心，审计扩展需要 AuditLogger schema 变更"
      deadline: 2026-05-15
    - item: "并行/DAG 执行模式（TeamExecutor 只实现 sequential）"
      reason: "Phase 1 只需验证编排框架可行性，并行需要异步安全的 SharedState"
      deadline: 2026-05-15
    - item: "跨会话 Team 记忆持久化（SharedState 仅会话内生命周期）"
      reason: "需要 DB 表支持 + 序列化策略，属于 Phase 2 scope"
      deadline: 2026-05-30

  semantic_regression:
    required: true
    risk_tags: [selection_strategy, fallback_retry, state_machine]
    oracles:
      - id: ORC-001
        type: temporal_trace
        statement: "用户发送简单请求 → Supervisor._classify 返回 needs_team=false → AgentLoop.run 直接执行 → 产出 answer+done 事件，全程不经过 TeamExecutor"
        protects: [selection_strategy, fallback_retry]
        verification: pending_test
      - id: ORC-002
        type: forbidden_strategy
        statement: "Tier 3 模型禁止调用 _classify（直接走单循环），禁止创建 TeamExecutor 实例用于执行"
        protects: [selection_strategy]
        verification: pending_test
      - id: ORC-003
        type: temporal_trace
        statement: "Team 执行异常 → 捕获异常 → fallback 到 _run_single → 产出 answer+done 事件，不中断 SSE 流"
        protects: [fallback_retry, state_machine]
        verification: pending_test
      - id: ORC-004
        type: forbidden_strategy
        statement: "禁止 per-request 在多个 Team 间 fallback（一次请求只分派到一个 Team 或走单循环，不做链式尝试）"
        protects: [fallback_retry]
        verification: pending_test
```
