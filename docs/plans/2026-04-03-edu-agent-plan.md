<!-- pre-takeover: archived for history, not active spec -->
# edu-agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace edu-cloud's existing ReAct agent with a Claude Code-inspired multi-tier agent kernel that supports planning, parallel tool execution, context compression, session memory, and dual-channel LLM routing.

**Architecture:** Bottom-up build in 7 batches. Each batch produces testable, committable code. Foundation layer first (data structures + registry), then LLM adapter, tool execution pipeline, intelligence layer (planning + memory), and finally the agent loop that wires everything together. Last batch migrates all 39 existing tools to the new interface.

**Tech Stack:** Python 3.11+ / asyncio / FastAPI / SQLAlchemy async / httpx / Pydantic

**Design Doc:** `docs/plans/2026-04-03-edu-agent-design.md`

---

```yaml
contract_pack:
  invariants:
    - id: INV-001
      statement: "旧工具签名 func(**kwargs) 在 Batch 6 迁移完成前持续可用，现有 agent.py 和 test_registry.py 全绿"
      verification: pending_test
      note: "Task 2 的 execute() 双签名保证，Batch 6 完成后删除旧路径"
    - id: INV-002
      statement: "capability 缺省语义为'无记录默认允许'：caps 中不存在的 key 不拒绝工具"
      verification: existing_test
      test_ref: "tests/test_ai/test_tool_access.py::test_capability_default_allow"
    - id: INV-003
      statement: "39 个工具全部通过 ToolRegistry.list_tools() 可发现，且通过 RBAC + Module + Capability 三重过滤"
      verification: pending_test
      note: "Task 30 最终集成测试验证"
    - id: INV-004
      statement: "SSE 事件流向前兼容：旧 answer/tool_call/tool_result/done 事件格式不变，新增 thinking/plan/task_update 为追加类型"
      verification: pending_test
      note: "Task 14 集成测试验证"
    - id: INV-005
      statement: "碰过 student 敏感度工具的会话锁定到主通道，后续所有 LLM 调用不流向增强通道"
      verification: pending_test
      note: "Task 7 测试 test_student_tool_locks_channel 验证"
  counter_examples:
    - id: CE-001
      scenario: "registry.execute() 只保留新签名 (input, ctx)，旧 agent.py 用 **kwargs 调用时参数丢失，工具返回空结果但不报错"
      tests_that_still_pass: "test_registry_v2.py 全通过（只测新签名）"
      mitigation: "Task 2 测试同时跑 test_registry_v2.py 和 test_registry.py，确认双签名并存"
    - id: CE-002
      scenario: "_check_capabilities 用 caps.get(req, False) 实现，未初始化 capability 的学校所有 requires_capabilities 工具被静默过滤"
      tests_that_still_pass: "test_tool_access_v2.py 中 test_capability_denied 通过（测的是显式 False）"
      mitigation: "Task 3 测试 test_capability_default_allow 验证空 caps 不拒绝"
    - id: CE-003
      scenario: "AgentLoop 只实现 answer/tool_calls 路径，plan 分支被跳过。用户发'全面分析三年级'时 Agent 直接单步回答，不做任务规划"
      tests_that_still_pass: "test_simple_answer 和 test_tool_call_and_answer 通过"
      mitigation: "Task 13 增加 test_plan_branch 验证规划路径"
  risk_modules:
    - module: src/edu_cloud/ai/registry.py
      reason: "工具注册+执行入口，接口变更影响 39 个工具 + agent.py + 所有工具测试"
    - module: src/edu_cloud/ai/tool_access.py
      reason: "三层权限过滤，默认语义变更会影响所有学校的工具可见性"
    - module: src/edu_cloud/ai/agent_loop.py
      reason: "核心循环，设计 §3 状态机实现，所有 Agent 功能的枢纽"
    - module: src/edu_cloud/api/ai.py
      reason: "唯一公共 API 入口，SSE 事件格式面向前端"
  test_debt: []
```

## Batch 1: Foundation Layer

> ToolContext, ToolResult, ToolSpec, ToolRegistry, ToolAccessResolver, AgentEvent schemas.
> Everything else depends on this batch.

### Task 1: ToolContext and ToolResult data structures

**Files:**
- Create: `src/edu_cloud/ai/tool_context.py`
- Test: `tests/test_ai/test_tool_context.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_tool_context.py
import pytest
from edu_cloud.ai.tool_context import ToolContext, ToolResult


def test_tool_result_success():
    r = ToolResult(success=True, data={"avg": 85.2})
    assert r.success is True
    assert r.data == {"avg": 85.2}
    assert r.error is None
    assert r.is_read_only is True


def test_tool_result_failure():
    r = ToolResult(success=False, data=None, error="exam not found")
    assert r.success is False
    assert r.error == "exam not found"


def test_tool_result_to_dict():
    r = ToolResult(success=True, data={"count": 3}, metadata={"duration_ms": 42})
    d = r.to_dict()
    assert d["success"] is True
    assert d["data"] == {"count": 3}
    assert d["metadata"]["duration_ms"] == 42


def test_tool_context_fields():
    ctx = ToolContext(
        db=None,
        school_id="S001",
        user_id="U001",
        role="academic_director",
        class_ids=["C1", "C2"],
        subject_codes=["SX"],
        grade_ids=None,
        capabilities={("analytics", "read"): True},
        enabled_modules=["exam", "grading"],
        anonymizer=None,
    )
    assert ctx.school_id == "S001"
    assert ctx.role == "academic_director"
    assert ctx.class_ids == ["C1", "C2"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_tool_context.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'edu_cloud.ai.tool_context'`

- [ ] **Step 3: Implement tool_context.py**

```python
# src/edu_cloud/ai/tool_context.py
"""Standardized tool execution context and result types (Design §4)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class ToolContext:
    """Injected into every tool call. Replaces the old _db/_school_id/**kwargs pattern."""

    db: AsyncSession
    school_id: str
    user_id: str
    role: str
    class_ids: list[str] | None = None
    subject_codes: list[str] | None = None
    grade_ids: list[str] | None = None
    capabilities: dict[tuple[str, str], bool] = field(default_factory=dict)
    enabled_modules: list[str] = field(default_factory=list)
    anonymizer: Any | None = None  # Anonymizer (avoid circular import)


@dataclass
class ToolResult:
    """Unified return type for all tools."""

    success: bool
    data: dict | list | str | None = None
    error: str | None = None
    metadata: dict | None = None
    is_read_only: bool = True

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"success": self.success, "data": self.data}
        if self.error is not None:
            d["error"] = self.error
        if self.metadata is not None:
            d["metadata"] = self.metadata
        return d
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_tool_context.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/ai/tool_context.py tests/test_ai/test_tool_context.py
git commit -m "feat(agent): add ToolContext and ToolResult data structures"
```

**测试契约:**
1. ToolResult 成功/失败序列化
   - 入口: `ToolResult(success=True/False, ...).to_dict()`
   - 反例: 如果 to_dict 未处理 None metadata，会序列化为 `{"metadata": null}` 而非省略
   - 边界: data=None / error=None / metadata=None
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_tool_context.py::test_tool_result_to_dict -v`
2. ToolContext 字段完整性
   - 入口: `ToolContext(db=..., school_id=..., ...)`
   - 反例: 如果遗漏 capabilities 字段默认值，构造时无 capabilities 参数会 TypeError
   - 边界: class_ids=None / capabilities={} / enabled_modules=[]
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_tool_context.py::test_tool_context_fields -v`

**边界条件:**
- data=None 且 success=True → 期望: to_dict 返回 `{"success": True, "data": None}`
- metadata 为空 dict → 期望: to_dict 包含 `"metadata": {}`
- error=None 且 success=False → 期望: to_dict 不包含 error key（或 error=None）

---

### Task 2: Refactor ToolSpec and ToolRegistry

**Files:**
- Modify: `src/edu_cloud/ai/registry.py`
- Modify: `tests/test_ai/test_registry.py`

- [ ] **Step 1: Write failing tests for new ToolSpec fields and new register signature**

```python
# tests/test_ai/test_registry_v2.py
import pytest
from edu_cloud.ai.registry import ToolRegistry, ToolSpec
from edu_cloud.ai.tool_context import ToolContext, ToolResult


def test_toolspec_has_new_fields():
    spec = ToolSpec(
        name="test",
        description="test tool",
        parameters={},
        func=lambda i, c: None,
        category="general",
        domain="exam",
        is_read_only=True,
        sensitivity="school",
        risk_level="low",
        allowed_roles=None,
        requires_capabilities=[],
    )
    assert spec.is_read_only is True
    assert spec.sensitivity == "school"


@pytest.mark.asyncio
async def test_registry_register_new_style():
    reg = ToolRegistry()

    @reg.register(
        name="get_exam",
        description="Get exam",
        parameters={"exam_id": {"type": "string"}},
        domain="exam",
        is_read_only=True,
        sensitivity="school",
    )
    async def get_exam(input: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data={"id": input["exam_id"]})

    specs = reg.get_all_specs()
    assert len(specs) == 1
    assert specs[0].name == "get_exam"
    assert specs[0].is_read_only is True
    assert specs[0].sensitivity == "school"


@pytest.mark.asyncio
async def test_registry_execute_new_style():
    reg = ToolRegistry()

    @reg.register(name="add_nums", description="Add", parameters={}, is_read_only=True, sensitivity="public")
    async def add_nums(input: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data={"sum": input["a"] + input["b"]})

    ctx = ToolContext(db=None, school_id="S1", user_id="U1", role="teacher")
    result = await reg.execute("add_nums", {"a": 1, "b": 2}, ctx)
    assert result.success is True
    assert result.data["sum"] == 3


def test_registry_get_schemas_includes_new_fields():
    reg = ToolRegistry()

    @reg.register(name="t1", description="Tool 1", parameters={"x": {"type": "int"}}, sensitivity="student", is_read_only=True)
    async def t1(input: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data=None)

    schemas = reg.get_schemas()
    assert len(schemas) == 1
    assert schemas[0]["function"]["name"] == "t1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_registry_v2.py -v`
Expected: FAIL (ToolSpec missing new fields, execute() signature mismatch)

- [ ] **Step 3: Rewrite registry.py with new ToolSpec and ToolRegistry**

```python
# src/edu_cloud/ai/registry.py
"""Tool registration and discovery (Design §4)."""
from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from edu_cloud.ai.tool_context import ToolContext, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict
    func: Callable[[dict, ToolContext], Awaitable[ToolResult]]
    category: str = "general"
    module_code: str | None = None
    domain: str = "general"
    requires_capabilities: list[tuple[str, str]] = field(default_factory=list)
    risk_level: str = "low"
    allowed_roles: list[str] | None = None
    is_read_only: bool = True
    sensitivity: str = "school"  # "public" | "school" | "student"


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict | None = None,
        category: str = "general",
        module_code: str | None = None,
        domain: str = "general",
        requires_capabilities: list[tuple] | None = None,
        risk_level: str = "low",
        allowed_roles: list[str] | None = None,
        is_read_only: bool = True,
        sensitivity: str = "school",
    ):
        def decorator(func: Callable):
            self._tools[name] = ToolSpec(
                name=name,
                description=description,
                parameters=parameters or {},
                func=func,
                category=category,
                module_code=module_code,
                domain=domain,
                requires_capabilities=list(requires_capabilities or []),
                risk_level=risk_level,
                allowed_roles=allowed_roles,
                is_read_only=is_read_only,
                sensitivity=sensitivity,
            )
            return func
        return decorator

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def get_all_specs(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def get_schemas(self, categories: list[str] | None = None) -> list[dict]:
        specs = self.get_all_specs()
        if categories:
            specs = [s for s in specs if s.category in categories]
        return [
            {
                "type": "function",
                "function": {
                    "name": s.name,
                    "description": s.description,
                    "parameters": {
                        "type": "object",
                        "properties": s.parameters,
                    },
                },
            }
            for s in specs
        ]

    async def execute(self, name: str, arguments: dict[str, Any], ctx_or_none=None, **injected) -> Any:
        spec = self._tools.get(name)
        if spec is None:
            if ctx_or_none is not None:
                return ToolResult(success=False, error=f"Unknown tool: {name}")
            return {"error": f"Unknown tool: {name}"}
        try:
            if isinstance(ctx_or_none, ToolContext):
                # New-style call: func(input, ctx) -> ToolResult
                result = spec.func(arguments, ctx_or_none)
                if inspect.isawaitable(result):
                    result = await result
                return result
            else:
                # Legacy call: func(**kwargs) -> dict (backward compat until Batch 6)
                func = spec.func
                sig = inspect.signature(func)
                kwargs = {}
                for param_name, param in sig.parameters.items():
                    if param_name.startswith("_"):
                        if param_name in injected:
                            kwargs[param_name] = injected[param_name]
                    elif param_name in arguments:
                        kwargs[param_name] = arguments[param_name]
                if inspect.iscoroutinefunction(func):
                    return await func(**kwargs)
                return func(**kwargs)
        except Exception as exc:
            logger.exception("Tool %s execution failed", name)
            if isinstance(ctx_or_none, ToolContext):
                return ToolResult(success=False, error=str(exc))
            return {"error": str(exc)}


# Global registry instance
tools = ToolRegistry()
```

- [ ] **Step 4: Run new tests + existing registry tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_registry_v2.py tests/test_ai/test_registry.py -v`
Expected: test_registry_v2.py all PASS. test_registry.py all PASS (dual-signature execute() supports both new ToolContext and legacy **kwargs call patterns). INV-001 verified.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/ai/registry.py tests/test_ai/test_registry_v2.py
git commit -m "feat(agent): refactor ToolSpec with is_read_only + sensitivity, ToolRegistry new execute()"
```

**测试契约:**
1. 新签名 execute(name, args, ToolContext) 返回 ToolResult
   - 入口: `await registry.execute("tool", {...}, ctx)`
   - 反例: 如果 execute 不检查 isinstance(ctx_or_none, ToolContext)，旧签名调用会把 ctx 当 **kwargs 参数传
   - 边界: args={} / ctx 全字段为默认值 / 未注册工具名
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_registry_v2.py::test_registry_execute_new_style -v`
2. 旧签名 execute(name, args, **kwargs) 保持兼容 (INV-001)
   - 入口: `await registry.execute("tool", {"x": 1}, _db=db, _school_id=sid)`
   - 反例: 如果旧路径被删除，现有 agent.py 调用时参数被忽略，工具收到空 kwargs
   - 边界: injected 参数为空 / 参数名不以 _ 开头
   - 回归: 现有 test_registry.py 全部 PASS
   - 命令: `pytest tests/test_ai/test_registry.py -v`

**边界条件:**
- execute 传入不存在的 tool name → 期望: 新签名返回 ToolResult(success=False)，旧签名返回 {"error": ...}
- execute 传入 ctx_or_none=None（旧签名无 ToolContext）→ 期望: 走 legacy 路径
- 工具函数抛异常 → 期望: 捕获后返回 error 结果，不抛到调用方

---

### Task 3: Refactor ToolAccessResolver

**Files:**
- Modify: `src/edu_cloud/ai/tool_access.py`
- Create: `tests/test_ai/test_tool_access_v2.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_tool_access_v2.py
import pytest
from edu_cloud.ai.registry import ToolSpec
from edu_cloud.ai.tool_access import ToolAccessResolver
from edu_cloud.ai.tool_context import ToolContext, ToolResult


def _make_spec(name, allowed_roles=None, module_code=None, requires_capabilities=None, sensitivity="school"):
    async def _noop(input: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data=None)
    return ToolSpec(
        name=name, description=name, parameters={}, func=_noop,
        allowed_roles=allowed_roles, module_code=module_code,
        requires_capabilities=requires_capabilities or [],
        sensitivity=sensitivity, is_read_only=True,
    )


def test_rbac_filter():
    resolver = ToolAccessResolver()
    specs = [
        _make_spec("t1", allowed_roles=["admin"]),
        _make_spec("t2", allowed_roles=["teacher"]),
        _make_spec("t3", allowed_roles=None),  # open to all
    ]
    result = resolver.resolve(specs, role="teacher", enabled_modules=None, capabilities={})
    names = [s.name for s in result]
    assert "t1" not in names
    assert "t2" in names
    assert "t3" in names


def test_module_filter():
    resolver = ToolAccessResolver()
    specs = [
        _make_spec("t1", module_code="exam"),
        _make_spec("t2", module_code="grading"),
        _make_spec("t3"),  # no module
    ]
    result = resolver.resolve(specs, role="admin", enabled_modules={"exam"}, capabilities={})
    names = [s.name for s in result]
    assert "t1" in names
    assert "t2" not in names
    assert "t3" in names


def test_capability_filter():
    resolver = ToolAccessResolver()
    specs = [
        _make_spec("t1", requires_capabilities=[("analytics", "read")]),
        _make_spec("t2", requires_capabilities=[]),
    ]
    caps = {("analytics", "read"): True, ("analytics", "write"): False}
    result = resolver.resolve(specs, role="admin", enabled_modules=None, capabilities=caps)
    names = [s.name for s in result]
    assert "t1" in names
    assert "t2" in names


def test_capability_denied():
    resolver = ToolAccessResolver()
    specs = [
        _make_spec("t1", requires_capabilities=[("grading", "write")]),
    ]
    caps = {("grading", "write"): False}
    result = resolver.resolve(specs, role="admin", enabled_modules=None, capabilities=caps)
    assert len(result) == 0


def test_capability_default_allow():
    """未配置的 capability 默认允许（INV-002：与现有行为一致）"""
    resolver = ToolAccessResolver()
    specs = [
        _make_spec("t1", requires_capabilities=[("exam", "read")]),
    ]
    result = resolver.resolve(specs, role="admin", enabled_modules=None, capabilities={})
    assert len(result) == 1  # 空 caps → 默认允许
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_tool_access_v2.py -v`
Expected: FAIL (resolve() signature changed from async to sync, parameters differ)

- [ ] **Step 3: Rewrite tool_access.py**

```python
# src/edu_cloud/ai/tool_access.py
"""Three-layer tool permission filtering (Design §4)."""
from __future__ import annotations

from edu_cloud.ai.registry import ToolSpec


class ToolAccessResolver:
    def resolve(
        self,
        all_specs: list[ToolSpec],
        role: str,
        enabled_modules: set[str] | None,
        capabilities: dict[tuple[str, str], bool],
    ) -> list[ToolSpec]:
        result = []
        for spec in all_specs:
            # Layer 1: RBAC
            if spec.allowed_roles is not None and role not in spec.allowed_roles:
                continue
            # Layer 2: Module switch
            if enabled_modules is not None and spec.module_code is not None:
                if spec.module_code not in enabled_modules:
                    continue
            # Layer 3: Capability matrix
            if not self._check_capabilities(spec.requires_capabilities, capabilities):
                continue
            result.append(spec)
        return result

    @staticmethod
    def _check_capabilities(
        required: list[tuple[str, str]],
        caps: dict[tuple[str, str], bool],
    ) -> bool:
        # INV-002: "无记录默认允许" — 只有显式 False 才拒绝
        for req in required:
            if req in caps and not caps[req]:
                return False
        return True
```

- [ ] **Step 4: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_tool_access_v2.py -v`
Expected: All 5 tests PASS (including test_capability_default_allow verifying INV-002)

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/ai/tool_access.py tests/test_ai/test_tool_access_v2.py
git commit -m "feat(agent): refactor ToolAccessResolver to sync three-layer filter"
```

**测试契约:**
1. RBAC 层过滤只允许匹配角色的工具
   - 入口: `resolver.resolve(specs, role="teacher", ...)`
   - 反例: 如果 RBAC 检查遗漏 allowed_roles=None（对所有角色开放），None 会被当空列表处理，拒绝所有人
   - 边界: allowed_roles=None / allowed_roles=[] / role 不在列表中
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_tool_access_v2.py::test_rbac_filter -v`
2. Module 层过滤禁用模块的工具
   - 入口: `resolver.resolve(specs, ..., enabled_modules={"exam"})`
   - 反例: 如果 module_code=None 的工具也被 module 过滤，所有无模块归属的通用工具消失
   - 边界: enabled_modules=None（不过滤） / module_code=None / enabled_modules=空集
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_tool_access_v2.py::test_module_filter -v`
3. Capability 层保持默认允许语义 (INV-002)
   - 入口: `resolver.resolve(specs, ..., capabilities={})`
   - 反例: 如果用 caps.get(req, False)，未初始化的学校所有带 requires_capabilities 的工具被静默拒绝
   - 边界: capabilities={} / 显式 True / 显式 False
   - 回归: 现有 test_tool_access.py::test_capability_default_allow
   - 命令: `pytest tests/test_ai/test_tool_access_v2.py::test_capability_default_allow -v`

**边界条件:**
- specs 为空列表 → 期望: 返回空列表
- capabilities={} 且工具有 requires_capabilities → 期望: 默认允许（INV-002）
- enabled_modules=空集 且工具有 module_code → 期望: 被过滤掉

---

### Task 4: Extend AgentEvent schemas

**Files:**
- Modify: `src/edu_cloud/ai/schemas.py`
- Create: `tests/test_ai/test_schemas_v2.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_schemas_v2.py
from edu_cloud.ai.schemas import AgentEvent, Message, ToolCall, Transition


def test_agent_event_new_types():
    for event_type in ("thinking", "plan", "task_update", "tool_call", "tool_result", "answer", "error", "done"):
        e = AgentEvent(type=event_type, data={"test": True})
        d = e.to_dict()
        assert d["type"] == event_type
        assert d["data"]["test"] is True


def test_transition_enum():
    assert Transition.NEXT_TURN.value == "next_turn"
    assert Transition.COMPACT.value == "compact"
    assert Transition.DONE.value == "done"
    assert Transition.ERROR_RETRY.value == "error_retry"
    assert Transition.TIER_DOWNGRADE.value == "tier_downgrade"
    assert Transition.MAX_TURNS.value == "max_turns"
    assert Transition.BUDGET_EXHAUSTED.value == "budget_exhausted"


def test_message_dataclass():
    m = Message(role="user", content="hello")
    assert m.role == "user"
    assert m.content == "hello"
    assert m.tool_calls is None

    m2 = Message(role="assistant", content=None, tool_calls=[
        ToolCall(id="tc1", name="get_exam", arguments={"id": "1"}, _raw={})
    ])
    assert len(m2.tool_calls) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_schemas_v2.py -v`
Expected: FAIL (Transition and Message not yet defined in schemas.py)

- [ ] **Step 3: Extend schemas.py**

```python
# src/edu_cloud/ai/schemas.py
"""Agent event types, message types, and enumerations (Design §3)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    _raw: dict

    @classmethod
    def from_openai(cls, raw: dict) -> ToolCall:
        import json
        func = raw.get("function", {})
        args = func.get("arguments", "{}")
        if isinstance(args, str):
            args = json.loads(args)
        return cls(id=raw["id"], name=func.get("name", ""), arguments=args, _raw=raw)

    def to_openai(self) -> dict:
        import json
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.name, "arguments": json.dumps(self.arguments)},
        }


@dataclass
class Message:
    role: str
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            d["content"] = self.content
        if self.tool_calls:
            d["tool_calls"] = [tc.to_openai() for tc in self.tool_calls]
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.name:
            d["name"] = self.name
        return d


# Keep old name as alias for backward compatibility during migration
ChatMessage = Message


@dataclass
class AgentEvent:
    type: str  # thinking | plan | task_update | tool_call | tool_result | answer | error | done
    data: dict[str, Any]

    def to_dict(self) -> dict:
        return {"type": self.type, "data": self.data}


class Transition(Enum):
    NEXT_TURN = "next_turn"
    COMPACT = "compact"
    ERROR_RETRY = "error_retry"
    TIER_DOWNGRADE = "tier_downgrade"
    MAX_TURNS = "max_turns"
    BUDGET_EXHAUSTED = "budget_exhausted"
    DONE = "done"
```

- [ ] **Step 4: Run new tests + existing schema tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_schemas_v2.py tests/test_ai/test_schemas.py -v 2>/dev/null; python -m pytest tests/test_ai/test_schemas_v2.py -v`
Expected: test_schemas_v2.py all PASS. Old tests may need minor adaptation (ChatMessage alias keeps them working).

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/ai/schemas.py tests/test_ai/test_schemas_v2.py
git commit -m "feat(agent): extend schemas with Message, Transition enum, new AgentEvent types"
```

**测试契约:**
1. AgentEvent 支持全部 8 种事件类型
   - 入口: `AgentEvent(type="thinking", data={...}).to_dict()`
   - 反例: 如果 to_dict 对未知 type 抛异常，新增事件类型会导致 SSE 中断
   - 边界: data={} / data 含嵌套 dict / type 为空字符串
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_schemas_v2.py::test_agent_event_new_types -v`
2. Transition 枚举完整
   - 入口: `Transition.NEXT_TURN.value`
   - 反例: 如果遗漏 TIER_DOWNGRADE，AgentLoop 状态机无法表达降级转换
   - 边界: 枚举成员数量 = 7
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_schemas_v2.py::test_transition_enum -v`

**边界条件:**
- Message 的 content=None 且 tool_calls 非空 → 期望: to_dict 省略 content key
- ToolCall.from_openai 传入 arguments 为字符串 → 期望: 自动 json.loads 解析
- AgentEvent data 含非 ASCII 字符 → 期望: to_dict 正确保留中文

---

## Batch 2: LLM Adapter Layer

> LLMAdapter protocol, LLMProxyAdapter, CapabilityProbe, SensitivityRouter.

### Task 5: LLM Adapter protocol and LLMProxyAdapter

**Files:**
- Create: `src/edu_cloud/ai/llm_adapter.py`
- Test: `tests/test_ai/test_llm_adapter.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_llm_adapter.py
import json
import pytest
import httpx
from unittest.mock import AsyncMock, patch
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMRequest, LLMResponse, TokenUsage
from edu_cloud.ai.schemas import Message, ToolCall


def test_llm_request_defaults():
    req = LLMRequest(messages=[Message(role="user", content="hi")])
    assert req.temperature == 0.7
    assert req.max_tokens == 4096
    assert req.stream is True
    assert req.tools is None


def test_llm_response_fields():
    resp = LLMResponse(
        content="hello",
        tool_calls=None,
        usage=TokenUsage(input_tokens=10, output_tokens=5),
        stop_reason="end_turn",
    )
    assert resp.content == "hello"
    assert resp.usage.total == 15


@pytest.mark.asyncio
async def test_proxy_adapter_chat_basic():
    adapter = LLMProxyAdapter(base_url="http://localhost:8100", slot="primary")

    mock_response = httpx.Response(
        200,
        json={
            "choices": [{"message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
    )
    with patch.object(adapter._http, "post", new_callable=AsyncMock, return_value=mock_response):
        resp = await adapter.chat(LLMRequest(
            messages=[Message(role="user", content="hello")],
            stream=False,
        ))
    assert resp.content == "hi"
    assert resp.stop_reason == "end_turn"
    assert resp.usage.input_tokens == 10


@pytest.mark.asyncio
async def test_proxy_adapter_chat_with_tool_calls():
    adapter = LLMProxyAdapter(base_url="http://localhost:8100", slot="primary")

    mock_response = httpx.Response(
        200,
        json={
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "tc1",
                        "type": "function",
                        "function": {"name": "get_exam", "arguments": json.dumps({"exam_id": "E1"})},
                    }],
                },
                "finish_reason": "tool_calls",
            }],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10},
        },
    )
    with patch.object(adapter._http, "post", new_callable=AsyncMock, return_value=mock_response):
        resp = await adapter.chat(LLMRequest(
            messages=[Message(role="user", content="show exam")],
            tools=[{"type": "function", "function": {"name": "get_exam", "parameters": {}}}],
            stream=False,
        ))
    assert resp.content is None
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "get_exam"
    assert resp.stop_reason == "tool_use"


def test_proxy_adapter_capabilities_defaults():
    adapter = LLMProxyAdapter(base_url="http://localhost:8100", slot="primary")
    assert adapter.supports_tool_use() is True  # assume yes by default
    assert adapter.context_window_size() == 128_000  # default


def test_proxy_adapter_name():
    adapter = LLMProxyAdapter(base_url="http://localhost:8100", slot="primary")
    assert adapter.name() == "llm-proxy:primary"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_llm_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement llm_adapter.py**

```python
# src/edu_cloud/ai/llm_adapter.py
"""Unified LLM adapter — routes all calls through llm-proxy (Design §5)."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Protocol

import httpx

from edu_cloud.ai.schemas import Message, ToolCall

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class LLMRequest:
    messages: list[Message]
    tools: list[dict] | None = None
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4096
    stream: bool = True


@dataclass
class LLMResponse:
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    usage: TokenUsage = field(default_factory=TokenUsage)
    stop_reason: str = "end_turn"
    raw: dict | None = None


@dataclass
class LLMChunk:
    """One chunk in a streaming response."""
    delta_content: str | None = None
    delta_tool_call: dict | None = None
    finish_reason: str | None = None


class LLMAdapter(Protocol):
    """Protocol that all LLM adapters implement."""

    async def chat(self, request: LLMRequest) -> LLMResponse: ...
    async def chat_stream(self, request: LLMRequest) -> AsyncGenerator[LLMChunk, None]: ...
    def supports_tool_use(self) -> bool: ...
    def supports_parallel_tool_calls(self) -> bool: ...
    def context_window_size(self) -> int: ...
    def name(self) -> str: ...


class LLMProxyAdapter:
    """Calls llm-proxy via OpenAI-compatible API. Slot header selects the provider."""

    def __init__(
        self,
        base_url: str = "http://localhost:8100",
        slot: str = "primary",
        timeout: int = 120,
        context_window: int = 128_000,
    ):
        self._base_url = base_url.rstrip("/")
        self._slot = slot
        self._context_window = context_window
        self._http = httpx.AsyncClient(timeout=timeout)
        self._cached_capabilities: dict | None = None

    async def close(self):
        await self._http.aclose()

    def name(self) -> str:
        return f"llm-proxy:{self._slot}"

    def supports_tool_use(self) -> bool:
        if self._cached_capabilities:
            return self._cached_capabilities.get("tool_use", True)
        return True

    def supports_parallel_tool_calls(self) -> bool:
        if self._cached_capabilities:
            return self._cached_capabilities.get("parallel_tools", False)
        return False

    def context_window_size(self) -> int:
        return self._context_window

    def set_capabilities(self, caps: dict) -> None:
        self._cached_capabilities = caps
        if "context_window" in caps:
            self._context_window = caps["context_window"]

    async def chat(self, request: LLMRequest) -> LLMResponse:
        payload = self._build_payload(request)
        resp = await self._http.post(
            f"{self._base_url}/v1/chat/completions",
            headers={"X-Slot": self._slot},
            json=payload,
        )
        resp.raise_for_status()
        return self._parse_response(resp.json())

    async def chat_stream(self, request: LLMRequest) -> AsyncGenerator[LLMChunk, None]:
        payload = self._build_payload(request)
        payload["stream"] = True
        async with self._http.stream(
            "POST",
            f"{self._base_url}/v1/chat/completions",
            headers={"X-Slot": self._slot},
            json=payload,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                chunk_data = json.loads(data_str)
                delta = chunk_data.get("choices", [{}])[0].get("delta", {})
                yield LLMChunk(
                    delta_content=delta.get("content"),
                    delta_tool_call=delta.get("tool_calls", [None])[0] if delta.get("tool_calls") else None,
                    finish_reason=chunk_data.get("choices", [{}])[0].get("finish_reason"),
                )

    def _build_payload(self, request: LLMRequest) -> dict:
        payload: dict[str, Any] = {
            "messages": [m.to_dict() for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False,
        }
        if request.model:
            payload["model"] = request.model
        if request.tools:
            payload["tools"] = request.tools
        return payload

    @staticmethod
    def _parse_response(data: dict) -> LLMResponse:
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage_raw = data.get("usage", {})

        # Parse tool calls
        tool_calls = None
        raw_tcs = message.get("tool_calls")
        if raw_tcs:
            tool_calls = [ToolCall.from_openai(tc) for tc in raw_tcs]

        # Map finish_reason
        finish = choice.get("finish_reason", "stop")
        stop_reason = "tool_use" if finish in ("tool_calls", "function_call") else "end_turn"

        return LLMResponse(
            content=message.get("content"),
            tool_calls=tool_calls,
            usage=TokenUsage(
                input_tokens=usage_raw.get("prompt_tokens", 0),
                output_tokens=usage_raw.get("completion_tokens", 0),
            ),
            stop_reason=stop_reason,
            raw=data,
        )
```

- [ ] **Step 4: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_llm_adapter.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/ai/llm_adapter.py tests/test_ai/test_llm_adapter.py
git commit -m "feat(agent): add LLMProxyAdapter with OpenAI-compatible llm-proxy integration"
```

**测试契约:**
1. chat() 解析 OpenAI 格式响应
   - 入口: `await adapter.chat(LLMRequest(messages=[...], stream=False))`
   - 反例: 如果 _parse_response 不处理 finish_reason="tool_calls"，tool_calls 响应会被当作普通回答
   - 边界: 空 choices / 缺失 usage / tool_calls=null
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_llm_adapter.py::test_proxy_adapter_chat_basic -v`
2. chat() 提取 tool_calls
   - 入口: `await adapter.chat(LLMRequest(messages=[...], tools=[...], stream=False))`
   - 反例: 如果 ToolCall.from_openai 不解析 arguments 字符串，tool 会收到未解析的 JSON 字符串
   - 边界: arguments="" / arguments="{}" / 多个 tool_calls
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_llm_adapter.py::test_proxy_adapter_chat_with_tool_calls -v`

**边界条件:**
- HTTP 响应 200 但 choices 为空数组 → 期望: content=None, tool_calls=None
- finish_reason 为 "function_call"（旧格式）→ 期望: stop_reason 映射为 "tool_use"
- response 缺失 usage 字段 → 期望: 默认 TokenUsage(0, 0)

---

### Task 6: CapabilityProbe

**Files:**
- Create: `src/edu_cloud/ai/capability_probe.py`
- Test: `tests/test_ai/test_capability_probe.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_capability_probe.py
import pytest
from unittest.mock import AsyncMock
from edu_cloud.ai.capability_probe import CapabilityProbe, LoopStrategy
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMResponse, TokenUsage
from edu_cloud.ai.schemas import ToolCall


def test_loop_strategy_tier1():
    s = LoopStrategy.for_tier(1)
    assert s.max_turns == 25
    assert s.parallel_tools is True
    assert s.task_planning is True
    assert s.self_verify is True
    assert s.context_compact is True
    assert s.memory_extract is True


def test_loop_strategy_tier2():
    s = LoopStrategy.for_tier(2)
    assert s.max_turns == 15
    assert s.task_planning is True
    assert s.self_verify is False
    assert s.sub_agents is False


def test_loop_strategy_tier3():
    s = LoopStrategy.for_tier(3)
    assert s.max_turns == 8
    assert s.parallel_tools is False
    assert s.task_planning is False


@pytest.mark.asyncio
async def test_probe_tier1():
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary", context_window=200_000)
    adapter.chat = AsyncMock(return_value=LLMResponse(
        tool_calls=[ToolCall(id="t1", name="test_tool", arguments={"x": 1}, _raw={})],
        usage=TokenUsage(10, 5),
        stop_reason="tool_use",
    ))
    probe = CapabilityProbe()
    tier = await probe.determine_tier(adapter)
    assert tier == 1


@pytest.mark.asyncio
async def test_probe_tier2():
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary", context_window=64_000)
    adapter.chat = AsyncMock(return_value=LLMResponse(
        tool_calls=[ToolCall(id="t1", name="test_tool", arguments={"x": 1}, _raw={})],
        usage=TokenUsage(10, 5),
        stop_reason="tool_use",
    ))
    probe = CapabilityProbe()
    tier = await probe.determine_tier(adapter)
    assert tier == 2


@pytest.mark.asyncio
async def test_probe_tier3_no_tool_use():
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary", context_window=8_000)
    adapter.chat = AsyncMock(return_value=LLMResponse(
        content="I cannot use tools",
        usage=TokenUsage(10, 5),
        stop_reason="end_turn",
    ))
    probe = CapabilityProbe()
    tier = await probe.determine_tier(adapter)
    assert tier == 3


@pytest.mark.asyncio
async def test_probe_tier3_on_error():
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    adapter.chat = AsyncMock(side_effect=Exception("connection refused"))
    probe = CapabilityProbe()
    tier = await probe.determine_tier(adapter)
    assert tier == 3


def test_probe_manual_override():
    probe = CapabilityProbe()
    probe.set_override(2)
    # override ignores adapter
    assert probe.get_tier() == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_capability_probe.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement capability_probe.py**

```python
# src/edu_cloud/ai/capability_probe.py
"""Detect LLM model capabilities and select agent loop tier (Design §5)."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMRequest
from edu_cloud.ai.schemas import Message

logger = logging.getLogger(__name__)

TIER_1_MIN_CONTEXT = 100_000
TIER_2_MIN_CONTEXT = 30_000


@dataclass(frozen=True)
class LoopStrategy:
    tier: int
    max_turns: int
    parallel_tools: bool
    task_planning: bool
    self_verify: bool
    sub_agents: bool
    context_compact: bool
    memory_extract: bool

    @classmethod
    def for_tier(cls, tier: int) -> LoopStrategy:
        if tier == 1:
            return cls(tier=1, max_turns=25, parallel_tools=True, task_planning=True,
                       self_verify=True, sub_agents=True, context_compact=True, memory_extract=True)
        if tier == 2:
            return cls(tier=2, max_turns=15, parallel_tools=True, task_planning=True,
                       self_verify=False, sub_agents=False, context_compact=True, memory_extract=False)
        return cls(tier=3, max_turns=8, parallel_tools=False, task_planning=False,
                   self_verify=False, sub_agents=False, context_compact=False, memory_extract=False)


class CapabilityProbe:
    def __init__(self):
        self._override: int | None = None
        self._cached_tier: int | None = None

    def set_override(self, tier: int) -> None:
        self._override = tier
        self._cached_tier = tier

    def get_tier(self) -> int:
        return self._cached_tier or 3

    async def determine_tier(self, adapter: LLMProxyAdapter) -> int:
        if self._override is not None:
            self._cached_tier = self._override
            return self._override

        has_tool_use = await self._test_tool_use(adapter)
        context_window = adapter.context_window_size()

        if has_tool_use and context_window >= TIER_1_MIN_CONTEXT:
            tier = 1
        elif has_tool_use and context_window >= TIER_2_MIN_CONTEXT:
            tier = 2
        else:
            tier = 3

        self._cached_tier = tier
        adapter.set_capabilities({
            "tool_use": has_tool_use,
            "parallel_tools": has_tool_use and context_window >= TIER_1_MIN_CONTEXT,
            "context_window": context_window,
        })
        logger.info("CapabilityProbe: tier=%d, tool_use=%s, context=%d", tier, has_tool_use, context_window)
        return tier

    async def _test_tool_use(self, adapter: LLMProxyAdapter) -> bool:
        try:
            resp = await adapter.chat(LLMRequest(
                messages=[Message(role="user", content="Call test_tool with x=1")],
                tools=[{
                    "type": "function",
                    "function": {
                        "name": "test_tool",
                        "description": "Test tool for capability probing",
                        "parameters": {"type": "object", "properties": {"x": {"type": "integer"}}},
                    },
                }],
                max_tokens=100,
                stream=False,
            ))
            return resp.tool_calls is not None and len(resp.tool_calls) > 0
        except Exception:
            logger.warning("CapabilityProbe: tool_use test failed, assuming no support")
            return False
```

- [ ] **Step 4: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_capability_probe.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/ai/capability_probe.py tests/test_ai/test_capability_probe.py
git commit -m "feat(agent): add CapabilityProbe with auto tier detection + manual override"
```

**测试契约:**
1. Tier 自动检测基于 context_window + tool_use
   - 入口: `await probe.determine_tier(adapter)`
   - 反例: 如果只看 context_window 不测 tool_use，一个不支持 tool_use 的 200K 模型会被判为 Tier 1
   - 边界: context_window=100000（边界值） / tool_use=False / adapter 抛异常
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_capability_probe.py -v`
2. LoopStrategy 各 tier 参数正确
   - 入口: `LoopStrategy.for_tier(1/2/3)`
   - 反例: 如果 tier 3 的 task_planning=True，低能力模型会尝试规划，浪费 token 且输出不可靠
   - 边界: tier=0（越界） / tier=4（越界）
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_capability_probe.py::test_loop_strategy_tier1 -v`

**边界条件:**
- adapter.chat 连续超时 → 期望: tier 降级到 3，不抛异常
- manual override 后调用 determine_tier → 期望: override 优先
- context_window 恰好等于 TIER_1_MIN_CONTEXT (100000) → 期望: 判为 Tier 1（含边界值）

---

### Task 7: SensitivityRouter

**Files:**
- Create: `src/edu_cloud/ai/sensitivity_router.py`
- Test: `tests/test_ai/test_sensitivity_router.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_sensitivity_router.py
import pytest
from edu_cloud.ai.sensitivity_router import SensitivityRouter
from edu_cloud.ai.llm_adapter import LLMProxyAdapter
from edu_cloud.ai.registry import ToolSpec
from edu_cloud.ai.schemas import Message
from edu_cloud.ai.tool_context import ToolContext, ToolResult
from dataclasses import dataclass


@dataclass
class FakeState:
    channel: str = "primary"


def _make_spec(name, sensitivity="school"):
    async def _noop(i, c):
        return ToolResult(success=True, data=None)
    return ToolSpec(name=name, description="", parameters={}, func=_noop, sensitivity=sensitivity, is_read_only=True)


def test_no_enhanced_channel():
    primary = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    router = SensitivityRouter(primary=primary, enhanced=None)
    state = FakeState()
    result = router.route(state, [_make_spec("t1", "public")])
    assert result is primary


def test_public_tools_use_enhanced():
    primary = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    enhanced = LLMProxyAdapter(base_url="http://test:8100", slot="enhanced")
    router = SensitivityRouter(primary=primary, enhanced=enhanced)
    state = FakeState()
    result = router.route(state, [_make_spec("t1", "public"), _make_spec("t2", "public")])
    assert result is enhanced


def test_school_tools_use_primary():
    primary = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    enhanced = LLMProxyAdapter(base_url="http://test:8100", slot="enhanced")
    router = SensitivityRouter(primary=primary, enhanced=enhanced)
    state = FakeState()
    result = router.route(state, [_make_spec("t1", "school")])
    assert result is primary


def test_student_tool_locks_channel():
    primary = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    enhanced = LLMProxyAdapter(base_url="http://test:8100", slot="enhanced")
    router = SensitivityRouter(primary=primary, enhanced=enhanced)
    state = FakeState()
    router.on_tool_executed(state, _make_spec("t1", "student"))
    assert state.channel == "primary_locked"

    # Even all-public tools now route to primary
    result = router.route(state, [_make_spec("t2", "public")])
    assert result is primary


def test_empty_tools_use_enhanced():
    primary = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    enhanced = LLMProxyAdapter(base_url="http://test:8100", slot="enhanced")
    router = SensitivityRouter(primary=primary, enhanced=enhanced)
    state = FakeState()
    result = router.route(state, [])
    assert result is enhanced
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_sensitivity_router.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement sensitivity_router.py**

```python
# src/edu_cloud/ai/sensitivity_router.py
"""Dual-channel LLM routing based on data sensitivity (Design §5)."""
from __future__ import annotations

import logging
from typing import Any, Protocol

from edu_cloud.ai.llm_adapter import LLMProxyAdapter
from edu_cloud.ai.registry import ToolSpec

logger = logging.getLogger(__name__)

_SENSITIVITY_ORDER = {"public": 0, "school": 1, "student": 2}


class HasChannel(Protocol):
    channel: str


class SensitivityRouter:
    """Routes LLM calls to primary (domestic) or enhanced (premium) channel.

    Safety rule: once a student-sensitivity tool has been executed in the session,
    the channel is locked to primary for the remainder of the session.
    """

    def __init__(self, primary: LLMProxyAdapter, enhanced: LLMProxyAdapter | None):
        self.primary = primary
        self.enhanced = enhanced

    def route(self, state: HasChannel, tool_specs: list[ToolSpec]) -> LLMProxyAdapter:
        if self.enhanced is None:
            return self.primary

        if state.channel == "primary_locked":
            return self.primary

        if not tool_specs:
            return self.enhanced

        max_sensitivity = max(_SENSITIVITY_ORDER.get(s.sensitivity, 1) for s in tool_specs)
        if max_sensitivity == 0:  # all public
            return self.enhanced

        return self.primary

    def on_tool_executed(self, state: HasChannel, spec: ToolSpec) -> None:
        if spec.sensitivity == "student":
            state.channel = "primary_locked"
            logger.info("Channel locked to primary after student-sensitivity tool: %s", spec.name)
```

- [ ] **Step 4: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_sensitivity_router.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/ai/sensitivity_router.py tests/test_ai/test_sensitivity_router.py
git commit -m "feat(agent): add SensitivityRouter with dual-channel data protection"
```

**测试契约:**
1. Student 工具锁定通道 (INV-005)
   - 入口: `router.on_tool_executed(state, student_spec)` → `router.route(state, [public_spec])`
   - 反例: 如果锁定检查用 channel=="primary" 而非 "primary_locked"，锁定后仍可路由到 enhanced
   - 边界: 连续锁定两次 / enhanced=None / tool_specs=[]
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_sensitivity_router.py::test_student_tool_locks_channel -v`
2. 全 public 工具路由到 enhanced
   - 入口: `router.route(state, [public_spec1, public_spec2])`
   - 反例: 如果 max() 在空 tool_specs 上调用会抛 ValueError
   - 边界: tool_specs=[] / 混合 public+school / enhanced=None
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_sensitivity_router.py::test_public_tools_use_enhanced -v`

**边界条件:**
- enhanced=None → 期望: 始终返回 primary，不报错
- tool_specs=[] → 期望: 路由到 enhanced（无工具 = 无数据敏感性）
- 已锁定后再次 on_tool_executed(student) → 期望: 保持锁定，无异常

---

## Batch 3: Tool Execution Pipeline

> ToolExecutor + ToolOrchestrator — the engine that runs tools with permission checks, error handling, and concurrent/serial batching.

### Task 8: ToolExecutor and ToolOrchestrator

**Files:**
- Create: `src/edu_cloud/ai/tool_executor.py`
- Test: `tests/test_ai/test_tool_executor.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_tool_executor.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_tool_executor.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement tool_executor.py**

```python
# src/edu_cloud/ai/tool_executor.py
"""Tool execution pipeline with concurrent batching (Design §4)."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from edu_cloud.ai.registry import ToolRegistry, ToolSpec
from edu_cloud.ai.schemas import ToolCall
from edu_cloud.ai.tool_context import ToolContext, ToolResult

logger = logging.getLogger(__name__)

MAX_TOOL_CONCURRENCY = 10


@dataclass
class ToolBatch:
    calls: list[ToolCall]
    concurrent: bool


class ToolExecutor:
    """Executes a single tool call with error handling and timing."""

    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    async def run_one(self, call: ToolCall, ctx: ToolContext) -> ToolResult:
        spec = self._registry.get(call.name)
        if spec is None:
            return ToolResult(success=False, error=f"Unknown tool: {call.name}")

        start = time.monotonic()
        try:
            result = await spec.func(call.arguments, ctx)
            duration_ms = (time.monotonic() - start) * 1000
            if result.metadata is None:
                result.metadata = {}
            result.metadata["duration_ms"] = round(duration_ms, 1)
            return result
        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            logger.exception("Tool %s failed after %.1fms", call.name, duration_ms)
            return ToolResult(
                success=False,
                error=str(exc),
                metadata={"duration_ms": round(duration_ms, 1)},
            )


class ToolOrchestrator:
    """Partitions tool calls into concurrent/serial batches and executes them.

    Read-only tools run concurrently (up to MAX_TOOL_CONCURRENCY).
    Write tools run serially, one at a time.
    """

    def __init__(self, registry: ToolRegistry):
        self._registry = registry
        self._executor = ToolExecutor(registry)

    def partition(self, calls: list[ToolCall]) -> list[ToolBatch]:
        batches: list[ToolBatch] = []
        current_reads: list[ToolCall] = []

        for call in calls:
            spec = self._registry.get(call.name)
            is_read_only = spec.is_read_only if spec else True

            if is_read_only:
                current_reads.append(call)
            else:
                if current_reads:
                    batches.append(ToolBatch(calls=current_reads, concurrent=True))
                    current_reads = []
                batches.append(ToolBatch(calls=[call], concurrent=False))

        if current_reads:
            batches.append(ToolBatch(calls=current_reads, concurrent=True))

        return batches

    async def execute(self, batches: list[ToolBatch], ctx: ToolContext) -> list[ToolResult]:
        results: list[ToolResult] = []
        for batch in batches:
            if batch.concurrent and len(batch.calls) > 1:
                batch_results = await asyncio.gather(
                    *[self._executor.run_one(call, ctx) for call in batch.calls[:MAX_TOOL_CONCURRENCY]]
                )
                results.extend(batch_results)
            else:
                for call in batch.calls:
                    results.append(await self._executor.run_one(call, ctx))
        return results
```

- [ ] **Step 4: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_tool_executor.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/ai/tool_executor.py tests/test_ai/test_tool_executor.py
git commit -m "feat(agent): add ToolExecutor + ToolOrchestrator with concurrent batching"
```

**测试契约:**
1. Partition 将 read-only 工具分为并发批次
   - 入口: `orchestrator.partition([read_call1, write_call, read_call2])`
   - 反例: 如果 partition 不分割 write 前后的 reads，write 会和 reads 并发执行导致数据竞争
   - 边界: 全 read / 全 write / 单个 call / 未注册工具
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_tool_executor.py::test_partition_mixed -v`
2. Execute 并发执行 read 批次
   - 入口: `await orchestrator.execute(batches, ctx)`
   - 反例: 如果 concurrent batch 内用串行循环，性能退化但功能不变——测试难以捕获，靠 partition 测试保证
   - 边界: 空 batches / 单 call batch / 工具抛异常
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_tool_executor.py::test_orchestrator_execute -v`
3. 未知工具返回 error result
   - 入口: `await executor.run_one(ToolCall(name="nonexistent"), ctx)`
   - 反例: 如果未检查 spec is None 直接调用 spec.func，会抛 AttributeError 而非返回优雅错误
   - 边界: name="" / name=None
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_tool_executor.py::test_executor_unknown_tool -v`

**边界条件:**
- 工具执行时抛异常 → 期望: 返回 ToolResult(success=False, error=str(exc))，不中断批次
- 空 tool_calls 列表 → 期望: partition 返回空 batches，execute 返回空 results
- 超过 MAX_TOOL_CONCURRENCY (10) 的并发 reads → 期望: 截断到前 10 个

---

## Batch 4: Intelligence Layer

> ContextManager (compression + token counting), SessionMemoryExtractor, AgentMemory model, TaskPlanner.

### Task 9: ContextManager

**Files:**
- Create: `src/edu_cloud/ai/context_manager.py`
- Test: `tests/test_ai/test_context_manager.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_context_manager.py
import pytest
from unittest.mock import AsyncMock
from edu_cloud.ai.context_manager import ContextManager, TokenCounter
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMResponse, TokenUsage
from edu_cloud.ai.schemas import Message


def test_token_counter_chinese():
    count = TokenCounter.estimate("你好世界")
    assert count == 6  # 4 chars * 1.5 = 6


def test_token_counter_english():
    count = TokenCounter.estimate("hello world")
    assert count == 4  # 11 chars * 0.4 ≈ 4


def test_token_counter_mixed():
    count = TokenCounter.estimate("你好 world")
    assert count > 0


def test_token_counter_messages():
    msgs = [
        Message(role="system", content="你是助手"),
        Message(role="user", content="hello"),
    ]
    count = TokenCounter.estimate_messages(msgs)
    assert count > 0


def test_should_compact_false():
    cm = ContextManager()
    assert cm.should_compact(token_count=5000, context_window=128_000) is False


def test_should_compact_true():
    cm = ContextManager()
    # 128000 - 13000 - 20000 = 95000 threshold
    assert cm.should_compact(token_count=96_000, context_window=128_000) is True


@pytest.mark.asyncio
async def test_compact_preserves_system_and_recent():
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    adapter.chat = AsyncMock(return_value=LLMResponse(
        content="Summary: user asked about exams, key finding is avg=85",
        usage=TokenUsage(100, 50),
    ))

    messages = [
        Message(role="system", content="You are an assistant"),
        Message(role="user", content="old question 1"),
        Message(role="assistant", content="old answer 1"),
        Message(role="user", content="old question 2"),
        Message(role="assistant", content="old answer 2"),
        Message(role="user", content="old question 3"),
        Message(role="assistant", content="old answer 3"),
        Message(role="user", content="recent question 1"),
        Message(role="assistant", content="recent answer 1"),
        Message(role="user", content="recent question 2"),
        Message(role="assistant", content="recent answer 2"),
    ]

    cm = ContextManager()
    new_messages = await cm.compact(messages, adapter)

    # System prompt preserved
    assert new_messages[0].role == "system"
    assert new_messages[0].content == "You are an assistant"
    # Summary injected
    assert "Summary" in new_messages[1].content
    # Recent 4 turns (8 messages) preserved
    assert new_messages[-1].content == "recent answer 2"
    # Total messages: system + summary + 4 recent turns (8 msgs) = 10
    assert len(new_messages) < len(messages)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_context_manager.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement context_manager.py**

```python
# src/edu_cloud/ai/context_manager.py
"""Context compression and token management (Design §6)."""
from __future__ import annotations

import logging
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMRequest
from edu_cloud.ai.schemas import Message

logger = logging.getLogger(__name__)

COMPACT_BUFFER = 13_000
SUMMARY_MAX_TOKENS = 20_000
KEEP_RECENT_TURNS = 4  # turns = pairs of user+assistant


class TokenCounter:
    @staticmethod
    def estimate(text: str) -> int:
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 1.5 + other_chars * 0.4)

    @staticmethod
    def estimate_messages(messages: list[Message]) -> int:
        total = 0
        for m in messages:
            if m.content:
                total += TokenCounter.estimate(m.content)
            if m.tool_calls:
                total += len(str(m.tool_calls)) // 3
        return total


class ContextManager:
    def should_compact(self, token_count: int, context_window: int) -> bool:
        threshold = context_window - COMPACT_BUFFER - SUMMARY_MAX_TOKENS
        return token_count > threshold

    async def compact(self, messages: list[Message], adapter: LLMProxyAdapter) -> list[Message]:
        if len(messages) < 3:
            return messages

        # Find boundary: keep system + last KEEP_RECENT_TURNS turns
        keep_count = KEEP_RECENT_TURNS * 2  # user + assistant per turn
        if len(messages) - 1 <= keep_count:
            return messages

        system_msg = messages[0]
        early_messages = messages[1 : -keep_count]
        recent_messages = messages[-keep_count:]

        summary = await self._summarize(early_messages, adapter)
        return [system_msg, Message(role="assistant", content=summary), *recent_messages]

    async def _summarize(self, messages: list[Message], adapter: LLMProxyAdapter) -> str:
        prompt = (
            "请从以下对话中提取关键信息，按优先级保留：\n"
            "1. 已确认的数据发现（具体数字和结论）\n"
            "2. 用户的原始需求和约束\n"
            "3. 已完成的任务和未完成的任务\n"
            "4. 发现的异常和待验证的假设\n\n"
            "丢弃：工具调用的原始 JSON、重复的中间步骤、已被纠正的错误结论。\n"
            "用结构化列表输出，控制在 500 字以内。"
        )
        try:
            resp = await adapter.chat(LLMRequest(
                messages=[Message(role="system", content=prompt), *messages],
                max_tokens=2000,
                stream=False,
            ))
            return f"[对话摘要] {resp.content}"
        except Exception:
            logger.warning("Compact summarization failed, using fallback")
            contents = [m.content for m in messages if m.content]
            return f"[对话摘要 - 简略] 之前讨论了: {'; '.join(contents[:5])}"
```

- [ ] **Step 4: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_context_manager.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/ai/context_manager.py tests/test_ai/test_context_manager.py
git commit -m "feat(agent): add ContextManager with auto-compact and token estimation"
```

**测试契约:**
1. should_compact 基于 token 阈值判断
   - 入口: `cm.should_compact(token_count=96000, context_window=128000)`
   - 反例: 如果阈值计算不减去 SUMMARY_MAX_TOKENS，compact 后摘要可能超出上下文窗口
   - 边界: token_count=0 / context_window=0 / 恰好等于阈值
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_context_manager.py::test_should_compact_true -v`
2. compact 保留 system prompt + 最近 4 轮
   - 入口: `await cm.compact(messages, adapter)`
   - 反例: 如果 keep_count 计算错误（用 turns 而非 messages 数），会保留过多或过少消息
   - 边界: messages 少于 3 条 / 恰好等于 keep_count / system 消息不在首位
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_context_manager.py::test_compact_preserves_system_and_recent -v`

**边界条件:**
- messages 只有 2 条（system + user）→ 期望: 原样返回，不 compact
- LLM 摘要调用失败 → 期望: fallback 到简略摘要，不抛异常
- 纯中文 text token 估算 → 期望: 每字 1.5 token（"你好" = 3 tokens）

---

### Task 10: AgentMemory model + SessionMemoryExtractor

**Files:**
- Create: `src/edu_cloud/models/agent_memory.py`
- Create: `src/edu_cloud/ai/session_memory.py`
- Test: `tests/test_ai/test_session_memory.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_session_memory.py
import pytest
from unittest.mock import AsyncMock
from edu_cloud.ai.session_memory import SessionMemoryExtractor, MemoryEntry
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMResponse, TokenUsage
from edu_cloud.ai.schemas import Message
from edu_cloud.models.agent_memory import AgentMemory


def test_memory_entry_fields():
    entry = MemoryEntry(
        memory_type="finding",
        content="二班数学函数掌握度仅 38%",
        entity_type="class",
        entity_id="C002",
    )
    assert entry.memory_type == "finding"
    assert entry.entity_type == "class"


def test_agent_memory_model_has_fields():
    # Just verify the ORM class has the expected columns
    columns = {c.name for c in AgentMemory.__table__.columns}
    assert "school_id" in columns
    assert "session_id" in columns
    assert "user_id" in columns
    assert "memory_type" in columns
    assert "content" in columns
    assert "entity_type" in columns
    assert "entity_id" in columns
    assert "is_active" in columns


@pytest.mark.asyncio
async def test_extract_returns_memories():
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    adapter.chat = AsyncMock(return_value=LLMResponse(
        content='[{"type":"finding","content":"二班数学持续退步","entity_type":"class","entity_id":"C002"}]',
        usage=TokenUsage(100, 50),
    ))

    extractor = SessionMemoryExtractor()
    messages = [
        Message(role="user", content="分析三年级"),
        Message(role="assistant", content="二班数学退步严重"),
    ]
    entries = await extractor.extract(messages, adapter)
    assert len(entries) >= 1
    assert entries[0].memory_type == "finding"


@pytest.mark.asyncio
async def test_extract_handles_bad_json():
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    adapter.chat = AsyncMock(return_value=LLMResponse(
        content="This is not valid JSON",
        usage=TokenUsage(10, 5),
    ))

    extractor = SessionMemoryExtractor()
    entries = await extractor.extract([Message(role="user", content="test")], adapter)
    assert entries == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_session_memory.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create AgentMemory model**

```python
# src/edu_cloud/models/agent_memory.py
"""Persistent agent memory across sessions (Design §6)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class AgentMemory(Base, IdMixin, TimestampMixin):
    __tablename__ = "agent_memories"

    school_id: Mapped[str] = mapped_column(String(36), index=True)
    session_id: Mapped[str] = mapped_column(String(36))
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    memory_type: Mapped[str] = mapped_column(String(20))  # finding | preference | follow_up
    content: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # student | class | school
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
```

- [ ] **Step 4: Create SessionMemoryExtractor**

```python
# src/edu_cloud/ai/session_memory.py
"""Extract and persist key findings from agent sessions (Design §6)."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMRequest
from edu_cloud.ai.schemas import Message

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    memory_type: str  # finding | preference | follow_up
    content: str
    entity_type: str | None = None
    entity_id: str | None = None


class SessionMemoryExtractor:
    async def extract(self, messages: list[Message], adapter: LLMProxyAdapter) -> list[MemoryEntry]:
        prompt = (
            "从这段对话中提取值得跨会话记住的信息。返回 JSON 数组，每项包含：\n"
            '- type: "finding" | "preference" | "follow_up"\n'
            '- content: 一句话描述\n'
            '- entity_type: "student" | "class" | "school" | null\n'
            '- entity_id: 关联 ID 或 null\n\n'
            "只提取重要发现、用户偏好、待跟进事项。不要提取临时数据。\n"
            "如果没有值得记住的，返回空数组 []。"
        )
        try:
            resp = await adapter.chat(LLMRequest(
                messages=[Message(role="system", content=prompt), *messages],
                max_tokens=1000,
                stream=False,
            ))
            return self._parse(resp.content)
        except Exception:
            logger.warning("Memory extraction failed")
            return []

    @staticmethod
    def _parse(raw: str) -> list[MemoryEntry]:
        try:
            # Try to extract JSON from the response
            text = raw.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
            items = json.loads(text)
            if not isinstance(items, list):
                return []
            return [
                MemoryEntry(
                    memory_type=item.get("type", "finding"),
                    content=item.get("content", ""),
                    entity_type=item.get("entity_type"),
                    entity_id=item.get("entity_id"),
                )
                for item in items
                if item.get("content")
            ]
        except (json.JSONDecodeError, KeyError, TypeError):
            return []
```

- [ ] **Step 5: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_session_memory.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Register AgentMemory in Alembic model discovery chain**

Add `from edu_cloud.models.agent_memory import AgentMemory` to `alembic/env.py` (alongside existing model imports). Update `tests/test_alembic_migration.py` import list to include AgentMemory.

- [ ] **Step 7: Generate Alembic migration**

```bash
cd C:/Users/Administrator/edu-cloud
python -m alembic revision --autogenerate -m "add agent_memories table"
```

Verify the generated migration creates the `agent_memories` table with all columns (school_id, session_id, user_id, memory_type, content, entity_type, entity_id, expires_at, is_active).

- [ ] **Step 8: Run migration smoke test**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_alembic_migration.py -v`
Expected: PASS — upgrade/downgrade cycle includes agent_memories table.

- [ ] **Step 9: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/models/agent_memory.py src/edu_cloud/ai/session_memory.py tests/test_ai/test_session_memory.py alembic/
git commit -m "feat(agent): add AgentMemory model + SessionMemoryExtractor + Alembic migration"
```

**测试契约:**
1. SessionMemoryExtractor 解析 LLM JSON 输出
   - 入口: `await extractor.extract(messages, adapter)`
   - 反例: 如果 _parse 不处理 markdown 代码块包裹（```json...```），LLM 典型输出会解析失败返回空
   - 边界: LLM 返回非 JSON / 返回空数组 / 返回嵌套 JSON
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_session_memory.py::test_extract_returns_memories -v`
2. AgentMemory ORM 模型列完整
   - 入口: `AgentMemory.__table__.columns`
   - 反例: 如果遗漏 is_active 列，查询活跃记忆时无法过滤已归档条目
   - 边界: expires_at=None / entity_type=None
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_session_memory.py::test_agent_memory_model_has_fields -v`

**边界条件:**
- LLM 返回 "This is not valid JSON" → 期望: 返回空列表，不抛异常
- LLM 返回 `[]` → 期望: 返回空列表
- messages 为空列表 → 期望: 仍调用 LLM（prompt + 空会话），不崩溃

---

### Task 11: TaskPlanner

**Files:**
- Create: `src/edu_cloud/ai/task_planner.py`
- Test: `tests/test_ai/test_task_planner.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_task_planner.py
import json
import pytest
from unittest.mock import AsyncMock
from edu_cloud.ai.task_planner import TaskPlanner, Plan, Task
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMResponse, TokenUsage
from edu_cloud.ai.registry import ToolSpec
from edu_cloud.ai.tool_context import ToolContext, ToolResult


def _make_specs():
    async def _noop(i, c): return ToolResult(success=True, data=None)
    return [
        ToolSpec(name="get_exam_summary", description="Get exam summary", parameters={}, func=_noop,
                 is_read_only=True, sensitivity="school"),
        ToolSpec(name="get_class_stats", description="Get class stats", parameters={}, func=_noop,
                 is_read_only=True, sensitivity="school"),
        ToolSpec(name="generate_report", description="Generate report", parameters={}, func=_noop,
                 is_read_only=False, sensitivity="school", risk_level="medium"),
    ]


@pytest.mark.asyncio
async def test_maybe_plan_returns_none_for_simple():
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    adapter.chat = AsyncMock(return_value=LLMResponse(
        content='{"plan": null}',
        usage=TokenUsage(10, 5),
    ))
    planner = TaskPlanner()
    plan = await planner.maybe_plan("数学平均分多少", tier=2, adapter=adapter, available_tools=_make_specs())
    assert plan is None


@pytest.mark.asyncio
async def test_maybe_plan_returns_plan_for_complex():
    plan_json = json.dumps({"plan": [
        {"description": "收集成绩数据", "tools_hint": ["get_exam_summary", "get_class_stats"], "depends_on": []},
        {"description": "生成报告", "tools_hint": ["generate_report"], "depends_on": ["0"]},
    ]})
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    adapter.chat = AsyncMock(return_value=LLMResponse(
        content=plan_json,
        usage=TokenUsage(50, 30),
    ))
    planner = TaskPlanner()
    plan = await planner.maybe_plan("全面分析三年级", tier=2, adapter=adapter, available_tools=_make_specs())
    assert plan is not None
    assert len(plan.tasks) == 2
    assert plan.tasks[0].description == "收集成绩数据"
    assert plan.tasks[1].depends_on == ["0"]


@pytest.mark.asyncio
async def test_maybe_plan_skipped_for_tier3():
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    planner = TaskPlanner()
    plan = await planner.maybe_plan("全面分析", tier=3, adapter=adapter, available_tools=_make_specs())
    assert plan is None


def test_schedule_topological_order():
    planner = TaskPlanner()
    plan = Plan(goal="test", tasks=[
        Task(id="0", description="first"),
        Task(id="1", description="second", depends_on=["0"]),
        Task(id="2", description="third", depends_on=["1"]),
    ])
    order = list(planner.schedule(plan))
    assert [t.id for t in order] == ["0", "1", "2"]


def test_schedule_parallel_independent():
    planner = TaskPlanner()
    plan = Plan(goal="test", tasks=[
        Task(id="0", description="a"),
        Task(id="1", description="b"),
        Task(id="2", description="c", depends_on=["0", "1"]),
    ])
    order = list(planner.schedule(plan))
    ids = [t.id for t in order]
    assert ids[-1] == "2"
    assert set(ids[:2]) == {"0", "1"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_task_planner.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement task_planner.py**

```python
# src/edu_cloud/ai/task_planner.py
"""Task decomposition and scheduling for complex goals (Design §7)."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Generator

from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMRequest
from edu_cloud.ai.registry import ToolSpec
from edu_cloud.ai.schemas import Message

logger = logging.getLogger(__name__)


@dataclass
class Task:
    id: str
    description: str
    status: str = "pending"
    tools_hint: list[str] | None = None
    depends_on: list[str] | None = None
    result_summary: str | None = None
    verify: str | None = None


@dataclass
class Plan:
    goal: str
    tasks: list[Task]
    current_task_index: int = 0


class TaskPlanner:
    async def maybe_plan(
        self,
        goal: str,
        tier: int,
        adapter: LLMProxyAdapter,
        available_tools: list[ToolSpec],
    ) -> Plan | None:
        if tier == 3:
            return None

        tool_desc = "\n".join(f"- {t.name}: {t.description}" for t in available_tools)
        prompt = (
            "你是任务规划器。用户给你一个目标，你判断：\n"
            '- 如果一步就能完成，回复 {"plan": null}\n'
            "- 如果需要多步，回复：\n"
            '{"plan": [{"description": "...", "tools_hint": ["..."], "depends_on": ["task_id"], "verify": "..."}]}\n\n'
            f"可用工具：\n{tool_desc}\n\n"
            "规划原则：每个任务是一个可独立验证的步骤；无依赖关系的任务可并行。"
        )

        try:
            resp = await adapter.chat(LLMRequest(
                messages=[Message(role="system", content=prompt), Message(role="user", content=goal)],
                max_tokens=1500,
                stream=False,
            ))
            data = json.loads(resp.content)
            if data.get("plan") is None:
                return None

            tasks = [
                Task(
                    id=str(i),
                    description=t["description"],
                    tools_hint=t.get("tools_hint"),
                    depends_on=t.get("depends_on", []),
                    verify=t.get("verify") if tier == 1 else None,
                )
                for i, t in enumerate(data["plan"])
            ]
            return Plan(goal=goal, tasks=tasks)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("Plan parsing failed: %s", exc)
            return None

    def schedule(self, plan: Plan) -> Generator[Task, None, None]:
        completed: set[str] = set()
        remaining = list(plan.tasks)

        while remaining:
            ready = [t for t in remaining if all(d in completed for d in (t.depends_on or []))]
            if not ready:
                logger.error("Task dependency deadlock: %s", [t.id for t in remaining])
                yield from remaining
                return
            for task in ready:
                yield task
                completed.add(task.id)
                remaining.remove(task)
```

- [ ] **Step 4: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_task_planner.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/ai/task_planner.py tests/test_ai/test_task_planner.py
git commit -m "feat(agent): add TaskPlanner with LLM-driven decomposition and topological scheduling"
```

**测试契约:**
1. maybe_plan 对简单问题返回 None
   - 入口: `await planner.maybe_plan("数学平均分多少", tier=2, adapter, tools)`
   - 反例: 如果 maybe_plan 不检查 `{"plan": null}`，会尝试解析 null 为 task 列表导致 TypeError
   - 边界: LLM 返回非 JSON / tier=3（跳过规划） / available_tools=[]
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_task_planner.py::test_maybe_plan_returns_none_for_simple -v`
2. schedule 按拓扑序产出任务
   - 入口: `list(planner.schedule(plan))`
   - 反例: 如果 schedule 不检查依赖是否在 completed 中，有循环依赖时会无限循环
   - 边界: 无依赖（全并行） / 线性链 / 循环依赖（死锁检测）
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_task_planner.py::test_schedule_topological_order -v`

**边界条件:**
- tier=3 → 期望: 直接返回 None，不调用 LLM
- LLM 返回 `{"plan": []}` （空 plan）→ 期望: 返回 Plan 但 tasks 为空（或 None）
- 循环依赖 A→B→A → 期望: 检测到死锁，仍然 yield 所有 remaining tasks

---

## Batch 5: Agent Loop + Prompts + API

> The core agent loop that wires everything together, system prompt templates, and API endpoint adaptation.

### Task 12: System prompt templates

**Files:**
- Create: `src/edu_cloud/ai/prompts.py`
- Test: `tests/test_ai/test_prompts.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_prompts.py
from edu_cloud.ai.prompts import build_teacher_prompt, build_compact_prompt


def test_teacher_prompt_contains_role():
    prompt = build_teacher_prompt(
        role="academic_director",
        display_name="张老师",
        school_name="实验中学",
        tool_names=["get_exam_summary", "get_class_stats"],
        tier=2,
    )
    assert "张老师" in prompt
    assert "教务主任" in prompt
    assert "get_exam_summary" in prompt


def test_teacher_prompt_tier1_has_plan_instruction():
    prompt = build_teacher_prompt(role="teacher", display_name="李老师", school_name="一中",
                                  tool_names=["t1"], tier=1)
    assert "计划" in prompt or "plan" in prompt.lower()


def test_teacher_prompt_tier3_no_plan_instruction():
    prompt = build_teacher_prompt(role="teacher", display_name="王老师", school_name="二中",
                                  tool_names=["t1"], tier=3)
    assert "计划" not in prompt


def test_compact_prompt():
    prompt = build_compact_prompt()
    assert "关键信息" in prompt or "摘要" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_prompts.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement prompts.py**

```python
# src/edu_cloud/ai/prompts.py
"""System prompt templates for different agent scenarios (Design §8)."""
from __future__ import annotations

ROLE_CN = {
    "platform_admin": "平台管理员",
    "district_admin": "教育局管理员",
    "principal": "校长",
    "academic_director": "教务主任",
    "grade_leader": "年级组长",
    "homeroom_teacher": "班主任",
    "subject_teacher": "科任教师",
    "parent": "家长",
}


def build_teacher_prompt(
    role: str,
    display_name: str,
    school_name: str,
    tool_names: list[str],
    tier: int,
    memories: list[str] | None = None,
) -> str:
    role_cn = ROLE_CN.get(role, role)
    tools_list = "、".join(tool_names[:20])
    if len(tool_names) > 20:
        tools_list += f" 等 {len(tool_names)} 个工具"

    sections = [
        f"你是 {school_name} 的 AI 教学助手，正在为{role_cn} {display_name} 服务。",
        "",
        "## 可用工具",
        f"你可以调用以下工具获取数据和执行操作：{tools_list}",
        "",
        "## 行为准则",
        "- 用中文回复",
        "- 数据分析时给出具体数字，不要模糊表述",
        "- 发现异常时主动指出（如成绩骤降、缺考过多）",
        "- 涉及学生姓名时使用代号（S001 等），最终回复中会自动还原",
    ]

    if tier <= 2:
        sections.extend([
            "",
            "## 复杂任务处理",
            "如果用户的请求需要多步完成（如"全面分析三年级"），先输出一个任务计划：",
            '回复 JSON: {"plan": [{"description": "步骤描述", "tools_hint": ["工具名"], "depends_on": []}]}',
            "如果一步就能完成，直接调用工具回答。",
        ])

    if tier == 1:
        sections.extend([
            "",
            "## 自省验证",
            "完成分析后，检查结论是否合理：",
            "- 数据支撑是否充分？",
            "- 是否有缺考/转学/题目难度变化等干扰因素？",
            "- 如有疑问，主动调用工具交叉验证。",
        ])

    if memories:
        sections.extend([
            "",
            "## 历史记忆",
            "以下是之前会话中的重要发现：",
            *[f"- {m}" for m in memories],
        ])

    return "\n".join(sections)


def build_compact_prompt() -> str:
    return (
        "请从以下对话中提取关键信息，按优先级保留：\n"
        "1. 已确认的数据发现（具体数字和结论）\n"
        "2. 用户的原始需求和约束\n"
        "3. 已完成的任务和未完成的任务\n"
        "4. 发现的异常和待验证的假设\n\n"
        "丢弃：工具调用的原始 JSON、重复的中间步骤、已被纠正的错误结论。\n"
        "用结构化列表输出，控制在 500 字以内。"
    )
```

- [ ] **Step 4: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_prompts.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/ai/prompts.py tests/test_ai/test_prompts.py
git commit -m "feat(agent): add system prompt templates with tier-aware instructions"
```

**测试契约:**
1. Tier 1/2 prompt 包含计划指令
   - 入口: `build_teacher_prompt(role="teacher", ..., tier=1)`
   - 反例: 如果 tier 检查用 `==` 而非 `<=`，tier=2 不会得到计划指令
   - 边界: tier=1 / tier=2 / tier=3
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_prompts.py::test_teacher_prompt_tier1_has_plan_instruction -v`
2. Prompt 包含角色中文名和学校
   - 入口: `build_teacher_prompt(role="academic_director", display_name="张老师", school_name="实验中学", ...)`
   - 反例: 如果 ROLE_CN 映射遗漏角色，prompt 会显示原始英文 role 而非中文
   - 边界: role 不在 ROLE_CN 映射中 / tool_names 超过 20 个 / memories=None
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_prompts.py::test_teacher_prompt_contains_role -v`

**边界条件:**
- tool_names=[] → 期望: prompt 中工具段显示空串而非 crash
- memories=None → 期望: 不生成历史记忆段
- role="unknown_role" → 期望: fallback 显示原始 role 字符串

---

### Task 13: AgentLoop — the core

**Files:**
- Create: `src/edu_cloud/ai/agent_loop.py`
- Test: `tests/test_ai/test_agent_loop.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_agent_loop.py
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from edu_cloud.ai.agent_loop import AgentLoop, AgentState
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMResponse, TokenUsage
from edu_cloud.ai.registry import ToolRegistry
from edu_cloud.ai.tool_context import ToolContext, ToolResult
from edu_cloud.ai.schemas import Message, ToolCall, Transition, AgentEvent
from edu_cloud.ai.capability_probe import LoopStrategy


def _setup():
    reg = ToolRegistry()

    @reg.register(name="get_score", description="Get score", parameters={"exam_id": {"type": "string"}},
                  is_read_only=True, sensitivity="school")
    async def get_score(input: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data={"avg": 85.2})

    ctx = ToolContext(db=None, school_id="S1", user_id="U1", role="academic_director")
    return reg, ctx


@pytest.mark.asyncio
async def test_simple_answer():
    """LLM returns direct answer, no tools."""
    reg, ctx = _setup()
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    adapter.chat = AsyncMock(return_value=LLMResponse(
        content="数学平均分是 85.2 分",
        usage=TokenUsage(50, 30),
        stop_reason="end_turn",
    ))

    loop = AgentLoop(registry=reg, adapter=adapter, strategy=LoopStrategy.for_tier(3))
    events = []
    async for event in loop.run("数学平均分", ctx, tool_specs=reg.get_all_specs()):
        events.append(event)

    types = [e.type for e in events]
    assert "answer" in types
    assert "done" in types
    answer_event = next(e for e in events if e.type == "answer")
    assert "85.2" in answer_event.data["content"]


@pytest.mark.asyncio
async def test_tool_call_and_answer():
    """LLM calls a tool, then answers."""
    reg, ctx = _setup()
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")

    call_count = 0
    async def mock_chat(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return LLMResponse(
                tool_calls=[ToolCall(id="tc1", name="get_score", arguments={"exam_id": "E1"}, _raw={})],
                usage=TokenUsage(50, 30),
                stop_reason="tool_use",
            )
        return LLMResponse(
            content="平均分是 85.2",
            usage=TokenUsage(80, 40),
            stop_reason="end_turn",
        )

    adapter.chat = mock_chat

    loop = AgentLoop(registry=reg, adapter=adapter, strategy=LoopStrategy.for_tier(3))
    events = []
    async for event in loop.run("查考试成绩", ctx, tool_specs=reg.get_all_specs()):
        events.append(event)

    types = [e.type for e in events]
    assert "tool_call" in types
    assert "tool_result" in types
    assert "answer" in types


@pytest.mark.asyncio
async def test_max_turns_stops():
    """Loop stops when max_turns is reached."""
    reg, ctx = _setup()
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    # Always return tool_call, never answer
    adapter.chat = AsyncMock(return_value=LLMResponse(
        tool_calls=[ToolCall(id="tc1", name="get_score", arguments={"exam_id": "E1"}, _raw={})],
        usage=TokenUsage(10, 5),
        stop_reason="tool_use",
    ))

    strategy = LoopStrategy.for_tier(3)  # max_turns=8
    loop = AgentLoop(registry=reg, adapter=adapter, strategy=strategy)
    events = []
    async for event in loop.run("loop forever", ctx, tool_specs=reg.get_all_specs()):
        events.append(event)

    types = [e.type for e in events]
    assert "done" in types
    done_event = next(e for e in events if e.type == "done")
    assert done_event.data["turns"] <= strategy.max_turns + 1


@pytest.mark.asyncio
async def test_plan_branch():
    """Tier ≤ 2: AgentLoop produces plan + task_update events when planner returns a plan."""
    import json as _json
    reg, ctx = _setup()
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")

    plan_json = _json.dumps({"plan": [
        {"description": "收集成绩", "tools_hint": ["get_score"], "depends_on": []},
    ]})
    call_count = 0
    async def mock_chat(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Planner call — returns plan
            return LLMResponse(content=plan_json, usage=TokenUsage(30, 20))
        if call_count == 2:
            # Task execution — tool call
            return LLMResponse(
                tool_calls=[ToolCall(id="tc1", name="get_score", arguments={"exam_id": "E1"}, _raw={})],
                usage=TokenUsage(20, 10), stop_reason="tool_use",
            )
        # Final answer
        return LLMResponse(content="分析完成", usage=TokenUsage(20, 10), stop_reason="end_turn")

    adapter.chat = mock_chat

    strategy = LoopStrategy.for_tier(2)  # task_planning=True
    loop = AgentLoop(registry=reg, adapter=adapter, strategy=strategy)
    events = []
    async for event in loop.run("全面分析三年级", ctx, tool_specs=reg.get_all_specs()):
        events.append(event)

    types = [e.type for e in events]
    assert "plan" in types, f"Expected 'plan' event, got: {types}"
    assert "task_update" in types, f"Expected 'task_update' event, got: {types}"
    assert "done" in types


@pytest.mark.asyncio
async def test_thinking_event():
    """When LLM returns content alongside tool_calls, emit a thinking event."""
    reg, ctx = _setup()
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")

    call_count = 0
    async def mock_chat(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return LLMResponse(
                content="让我查一下成绩...",
                tool_calls=[ToolCall(id="tc1", name="get_score", arguments={"exam_id": "E1"}, _raw={})],
                usage=TokenUsage(30, 20), stop_reason="tool_use",
            )
        return LLMResponse(content="平均分 85.2", usage=TokenUsage(20, 10), stop_reason="end_turn")

    adapter.chat = mock_chat

    strategy = LoopStrategy.for_tier(3)
    loop = AgentLoop(registry=reg, adapter=adapter, strategy=strategy)
    events = []
    async for event in loop.run("查成绩", ctx, tool_specs=reg.get_all_specs()):
        events.append(event)

    types = [e.type for e in events]
    assert "thinking" in types, f"Expected 'thinking' event when content + tool_calls, got: {types}"


@pytest.mark.asyncio
async def test_error_count_threshold():
    """error_count >= 3 → yield error event and stop."""
    reg, ctx = _setup()
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    adapter.chat = AsyncMock(side_effect=Exception("connection refused"))

    strategy = LoopStrategy.for_tier(3)
    loop = AgentLoop(registry=reg, adapter=adapter, strategy=strategy)
    events = []
    async for event in loop.run("test", ctx, tool_specs=reg.get_all_specs()):
        events.append(event)

    types = [e.type for e in events]
    assert "error" in types
    assert "done" in types
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_agent_loop.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement agent_loop.py**

```python
# src/edu_cloud/ai/agent_loop.py
"""Core agent loop — plan, execute tools, verify, respond (Design §3).

Implements the full state machine: CapabilityProbe → SensitivityRouter →
plan branch (tier ≤ 2) → tool execution → thinking/plan/task_update events →
error threshold → memory extract.

Inspired by Claude Code's query.ts AsyncGenerator pattern.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import AsyncGenerator

from edu_cloud.ai.capability_probe import LoopStrategy
from edu_cloud.ai.context_manager import ContextManager, TokenCounter
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMRequest, LLMResponse
from edu_cloud.ai.registry import ToolRegistry, ToolSpec
from edu_cloud.ai.schemas import AgentEvent, Message, ToolCall, Transition
from edu_cloud.ai.sensitivity_router import SensitivityRouter
from edu_cloud.ai.session_memory import SessionMemoryExtractor
from edu_cloud.ai.task_planner import TaskPlanner
from edu_cloud.ai.tool_context import ToolContext
from edu_cloud.ai.tool_executor import ToolOrchestrator

logger = logging.getLogger(__name__)


@dataclass
class AgentState:
    messages: list[Message]
    turn_count: int = 0
    token_count: int = 0
    error_count: int = 0
    channel: str = "primary"


class AgentLoop:
    def __init__(
        self,
        registry: ToolRegistry,
        adapter: LLMProxyAdapter,
        strategy: LoopStrategy,
        sensitivity_router: SensitivityRouter | None = None,
        memory_extractor: SessionMemoryExtractor | None = None,
    ):
        self._registry = registry
        self._adapter = adapter
        self._strategy = strategy
        self._orchestrator = ToolOrchestrator(registry)
        self._context_mgr = ContextManager()
        self._planner = TaskPlanner()
        self._sensitivity_router = sensitivity_router
        self._memory_extractor = memory_extractor

    async def run(
        self,
        goal: str,
        ctx: ToolContext,
        *,
        tool_specs: list[ToolSpec],
        system_prompt: str = "",
        memories: list[str] | None = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        state = AgentState(messages=[])

        # Build initial messages
        if system_prompt:
            state.messages.append(Message(role="system", content=system_prompt))
        state.messages.append(Message(role="user", content=goal))
        state.token_count = TokenCounter.estimate_messages(state.messages)

        # Build tool schemas for LLM
        tool_schemas = [
            {
                "type": "function",
                "function": {"name": s.name, "description": s.description, "parameters": {"type": "object", "properties": s.parameters}},
            }
            for s in tool_specs
        ]

        # --- Plan branch (tier ≤ 2) ---
        plan = None
        if self._strategy.task_planning:
            plan = await self._planner.maybe_plan(
                goal, tier=self._strategy.tier, adapter=self._adapter, available_tools=tool_specs
            )
            if plan is not None:
                yield AgentEvent(type="plan", data={
                    "tasks": [{"id": t.id, "description": t.description} for t in plan.tasks],
                })

        # --- Main loop ---
        plan_tasks = list(self._planner.schedule(plan)) if plan else [None]
        for task in plan_tasks:
            if task is not None:
                yield AgentEvent(type="task_update", data={
                    "id": task.id, "description": task.description, "status": "in_progress",
                })
                # Inject task context into messages
                state.messages.append(Message(
                    role="user",
                    content=f"[任务 {task.id}] {task.description}",
                ))

            while state.turn_count < self._strategy.max_turns:
                state.turn_count += 1

                # Check if compaction needed
                if self._strategy.context_compact and self._context_mgr.should_compact(
                    state.token_count, self._adapter.context_window_size()
                ):
                    state.messages = await self._context_mgr.compact(state.messages, self._adapter)
                    state.token_count = TokenCounter.estimate_messages(state.messages)

                # Select adapter via SensitivityRouter
                active_adapter = self._adapter
                if self._sensitivity_router is not None:
                    active_adapter = self._sensitivity_router.route(state, tool_specs)

                # Call LLM
                try:
                    resp = await active_adapter.chat(LLMRequest(
                        messages=state.messages,
                        tools=tool_schemas if tool_schemas else None,
                        stream=False,
                    ))
                except Exception as exc:
                    state.error_count += 1
                    logger.error("LLM call failed (attempt %d): %s", state.error_count, exc)
                    if state.error_count >= 3:
                        yield AgentEvent(type="error", data={"message": f"LLM 调用失败: {exc}"})
                        break
                    continue

                state.token_count += (resp.usage.input_tokens + resp.usage.output_tokens)

                # Handle response
                if resp.content and resp.tool_calls:
                    # LLM produced thinking text alongside tool calls
                    yield AgentEvent(type="thinking", data={"content": resp.content})

                if resp.tool_calls:
                    # Tool calls
                    state.messages.append(Message(role="assistant", content=resp.content, tool_calls=resp.tool_calls))

                    for tc in resp.tool_calls:
                        yield AgentEvent(type="tool_call", data={"tool": tc.name, "args": tc.arguments, "id": tc.id})

                    # Execute tools
                    batches = self._orchestrator.partition(resp.tool_calls)
                    if not self._strategy.parallel_tools:
                        from edu_cloud.ai.tool_executor import ToolBatch
                        batches = [ToolBatch(calls=[c], concurrent=False) for c in resp.tool_calls]

                    results = await self._orchestrator.execute(batches, ctx)

                    # Notify SensitivityRouter of executed tools (channel lock)
                    for tc, result in zip(resp.tool_calls, results):
                        spec = self._registry.get(tc.name)
                        if spec and self._sensitivity_router:
                            self._sensitivity_router.on_tool_executed(state, spec)

                        state.messages.append(Message(
                            role="tool",
                            content=str(result.to_dict()),
                            tool_call_id=tc.id,
                            name=tc.name,
                        ))
                        yield AgentEvent(type="tool_result", data={
                            "tool": tc.name, "id": tc.id, "success": result.success,
                            "data": result.data, "error": result.error,
                        })

                    state.error_count = 0
                    continue

                if resp.stop_reason == "end_turn" and resp.content:
                    # Direct answer — if in plan mode, mark task complete and break inner loop
                    state.messages.append(Message(role="assistant", content=resp.content))
                    if task is not None:
                        yield AgentEvent(type="task_update", data={
                            "id": task.id, "status": "completed",
                        })
                    else:
                        yield AgentEvent(type="answer", data={"content": resp.content})
                    break

                # No content and no tool calls — unexpected
                logger.warning("LLM returned empty response at turn %d", state.turn_count)
                break

            # Check if error threshold was hit
            if state.error_count >= 3:
                break

        # If no plan and last event was not answer, emit the final answer from messages
        if plan is not None and state.messages:
            last_assistant = next(
                (m for m in reversed(state.messages) if m.role == "assistant" and m.content),
                None,
            )
            if last_assistant:
                yield AgentEvent(type="answer", data={"content": last_assistant.content})

        # --- Post-loop: memory extraction ---
        if self._strategy.memory_extract and self._memory_extractor is not None:
            try:
                await self._memory_extractor.extract(state.messages, self._adapter)
            except Exception:
                logger.warning("Post-loop memory extraction failed")

        yield AgentEvent(type="done", data={
            "turns": state.turn_count,
            "tokens": state.token_count,
            "channel": state.channel,
        })
```

- [ ] **Step 4: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_agent_loop.py -v`
Expected: All 7 tests PASS (simple_answer, tool_call_and_answer, max_turns, plan_branch, thinking_event, error_count_threshold)

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/ai/agent_loop.py tests/test_ai/test_agent_loop.py
git commit -m "feat(agent): add AgentLoop with full state machine — plan/thinking/sensitivity/memory"
```

**测试契约:**
1. 简单问答路径：LLM 直接回答
   - 入口: `async for event in loop.run("数学平均分", ctx, tool_specs=specs)`
   - 反例: 如果 run() 不 yield answer event，SSE 流无内容但 done 状态是 success
   - 边界: system_prompt="" / tool_specs=[] / goal 为空字符串
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_agent_loop.py::test_simple_answer -v`
2. 工具调用路径：LLM → tool_call → tool_result → answer
   - 入口: `async for event in loop.run("查成绩", ctx, tool_specs=specs)`
   - 反例: 如果 tool_result 未添加到 messages，LLM 第二轮看不到工具结果，无法生成答案
   - 边界: 工具返回 ToolResult(success=False) / 多个并发 tool_calls
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_agent_loop.py::test_tool_call_and_answer -v`
3. Plan 分支路径 (tier ≤ 2)
   - 入口: `async for event in loop.run("全面分析", ctx, tool_specs=specs)` (strategy=tier2)
   - 反例: 如果 _planner.maybe_plan 被调用但返回的 plan 被忽略（CE-003），Agent 跳过规划直接单步回答
   - 边界: planner 返回 None（简单问题） / planner 返回空 tasks / tier=3（跳过规划）
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_agent_loop.py::test_plan_branch -v`
4. Thinking event 当 content + tool_calls 共存
   - 入口: `async for event in loop.run(...)` (LLM 返回 content 和 tool_calls)
   - 反例: 如果不检测 content+tool_calls 共存，thinking 内容被丢弃，前端无法展示推理过程
   - 边界: content="" + tool_calls / content=None + tool_calls
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_agent_loop.py::test_thinking_event -v`
5. error_count ≥ 3 → yield error + done
   - 入口: `async for event in loop.run(...)` (adapter 连续 3 次异常)
   - 反例: 如果 error_count 检查用 > 而非 >=，需要 4 次失败才停止
   - 边界: error_count=2 后成功恢复 / max_turns 先触达
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_agent_loop.py::test_error_count_threshold -v`

**边界条件:**
- tool_specs=[] → 期望: LLM 无工具可调用，直接回答
- max_turns=1 → 期望: 最多循环一次后 yield done
- LLM 返回空响应（no content, no tool_calls）→ 期望: break 循环，yield done

---

### Task 14: SSE event contract tests

**Files:**
- Test: `tests/test_ai/test_ai_api_v2.py`

> This task validates that all new AgentEvent types serialize correctly for SSE transport AND that the AgentLoop produces events consumable by an SSE endpoint. The actual `api/ai.py` wiring happens in Batch 7 (Task 27), but the contract is locked here (INV-004).
>
> **Note (F003):** 入口级 SSE 契约测试（AsyncClient POST `/api/v1/ai/chat` 验证 SSE 流）在 Task 27 实现，因为 api/ai.py 的 AgentLoop wiring 在 Task 27 才发生。本 Task 仅验证 AgentEvent 序列化和 AgentLoop 事件产出。

- [ ] **Step 1: Write tests**

```python
# tests/test_ai/test_ai_api_v2.py
import json
import pytest
from unittest.mock import AsyncMock
from edu_cloud.ai.schemas import AgentEvent
from edu_cloud.ai.agent_loop import AgentLoop
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMResponse, TokenUsage
from edu_cloud.ai.registry import ToolRegistry
from edu_cloud.ai.tool_context import ToolContext, ToolResult
from edu_cloud.ai.capability_probe import LoopStrategy
from edu_cloud.ai.schemas import ToolCall


def test_agent_event_serialization_for_sse():
    """Verify all new event types serialize correctly for SSE."""
    events = [
        AgentEvent(type="thinking", data={"content": "分析中..."}),
        AgentEvent(type="plan", data={"tasks": [{"id": "0", "description": "收集数据"}]}),
        AgentEvent(type="task_update", data={"id": "0", "status": "in_progress"}),
        AgentEvent(type="tool_call", data={"tool": "get_exam", "args": {}}),
        AgentEvent(type="tool_result", data={"tool": "get_exam", "success": True, "data": {}}),
        AgentEvent(type="answer", data={"content": "分析结果..."}),
        AgentEvent(type="done", data={"turns": 3, "tokens": 5000}),
    ]
    for event in events:
        d = event.to_dict()
        assert "type" in d
        assert "data" in d
        line = f"data: {json.dumps(d, ensure_ascii=False)}\n\n"
        assert event.type in line


def test_sse_event_backward_compat():
    """INV-004: old event types (answer/tool_call/tool_result/done) format unchanged."""
    answer = AgentEvent(type="answer", data={"content": "回答"})
    d = answer.to_dict()
    assert d == {"type": "answer", "data": {"content": "回答"}}

    done = AgentEvent(type="done", data={"turns": 5, "tokens": 3000})
    d = done.to_dict()
    assert d["type"] == "done"
    assert "turns" in d["data"]
    assert "tokens" in d["data"]


@pytest.mark.asyncio
async def test_agentloop_produces_valid_sse_event_stream():
    """Integration: AgentLoop → collect events → simulate SSE serialization."""
    reg = ToolRegistry()

    @reg.register(name="get_score", description="Get score", parameters={"exam_id": {"type": "string"}},
                  is_read_only=True, sensitivity="school")
    async def get_score(input: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data={"avg": 85.2})

    ctx = ToolContext(db=None, school_id="S1", user_id="U1", role="teacher")
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")

    call_count = 0
    async def mock_chat(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return LLMResponse(
                tool_calls=[ToolCall(id="tc1", name="get_score", arguments={"exam_id": "E1"}, _raw={})],
                usage=TokenUsage(20, 10), stop_reason="tool_use",
            )
        return LLMResponse(content="平均分 85.2", usage=TokenUsage(20, 10), stop_reason="end_turn")

    adapter.chat = mock_chat

    loop = AgentLoop(registry=reg, adapter=adapter, strategy=LoopStrategy.for_tier(3))
    sse_lines = []
    async for event in loop.run("查成绩", ctx, tool_specs=reg.get_all_specs()):
        d = event.to_dict()
        line = f"data: {json.dumps(d, ensure_ascii=False)}\n\n"
        sse_lines.append(line)
        # Verify each line is valid SSE format
        assert line.startswith("data: ")
        assert line.endswith("\n\n")
        parsed = json.loads(line[6:].strip())
        assert "type" in parsed
        assert "data" in parsed

    # Verify event stream contains expected types
    types = [json.loads(line[6:].strip())["type"] for line in sse_lines]
    assert "tool_call" in types
    assert "tool_result" in types
    assert "answer" in types
    assert "done" in types
```

- [ ] **Step 2: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_ai_api_v2.py -v`
Expected: All 3 tests PASS

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add tests/test_ai/test_ai_api_v2.py
git commit -m "test(agent): add SSE event contract tests — serialization + integration + backward compat"
```

**测试契约:**
1. AgentEvent 全类型序列化 (INV-004)
   - 入口: `AgentEvent(type="thinking", data={...}).to_dict()`
   - 反例: 如果 to_dict 做类型白名单检查，新增事件类型会被拒绝
   - 边界: data 含嵌套 dict / data 含中文 / type 为空字符串
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_ai_api_v2.py::test_agent_event_serialization_for_sse -v`
2. SSE 向前兼容 (INV-004)
   - 入口: `AgentEvent(type="answer", data={...}).to_dict()`
   - 反例: 如果 to_dict 新增 "version" 等字段，旧前端解析会拿到意外 key
   - 边界: 旧 4 种事件类型的格式不变
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_ai_api_v2.py::test_sse_event_backward_compat -v`
3. AgentLoop → SSE 集成
   - 入口: `async for event in loop.run(...)` → `json.dumps(event.to_dict())`
   - 反例: 如果 AgentLoop yield 的 event.data 含不可 JSON 序列化的对象（如 datetime），SSE 序列化会 crash
   - 边界: 工具返回 data=None / 工具返回 data 含嵌套列表
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_ai_api_v2.py::test_agentloop_produces_valid_sse_event_stream -v`

**边界条件:**
- event.data 含 None 值 → 期望: json.dumps 正常序列化为 null
- event.type 为新增类型（如 "thinking"）→ 期望: SSE 格式不变，旧前端忽略即可
- 空事件流（AgentLoop 立即 done）→ 期望: 至少有 done 事件

---

## Batch 6: Tool Migration

> Migrate all 39 existing tools from the old `async def func(**kwargs)` signature to the new `async def func(input: dict, ctx: ToolContext) -> ToolResult` signature.

**测试契约（Batch 6 通用，适用 Task 15-26 所有工具迁移）:**
1. 迁移后工具签名接受 (input: dict, ctx: ToolContext) 并返回 ToolResult
   - 入口: `await tools.execute("tool_name", {...}, ctx)`
   - 反例: 如果签名未改但仍用旧 **kwargs，ToolContext 参数会被忽略，输出 dict 而非 ToolResult
   - 边界: 空 input / ctx 全默认值 / 缺必填参数
   - 回归: 旧签名 **kwargs 在迁移前仍可用（INV-001 双签名保证）
   - 命令: `pytest tests/test_ai/test_tools_{module}.py -v`

**边界条件（Batch 6 通用）:**
- input={} （所有可选参数缺失）→ 期望: 使用默认值或返回合理错误，不抛 KeyError
- ctx.school_id 与 DB 数据不匹配 → 期望: 返回空结果或 ToolResult(success=False)
- 工具内部异常 → 期望: 被 try/except 包裹，返回 ToolResult(success=False, error=str(exc))

### Task 15: Migrate exam tools (3 tools)

**Files:**
- Modify: `src/edu_cloud/ai/tools/exams.py`
- Modify: `tests/test_ai/test_tools_exams.py` (adapt tests)

- [ ] **Step 1: Migrate each tool**

For each tool in `exams.py`, apply this mechanical transformation:

Before:
```python
@tools.register(name="get_exam_list", description="...", category="L1_exam", ...)
async def get_exam_list(status=None, *, _db=None, _school_id="", _visible_subjects=None):
    ...
    return {"exams": [...]}
```

After:
```python
@tools.register(name="get_exam_list", description="...", category="L1_exam", ..., is_read_only=True, sensitivity="school")
async def get_exam_list(input: dict, ctx: ToolContext) -> ToolResult:
    status = input.get("status")
    _db = ctx.db
    _school_id = ctx.school_id
    _visible_subjects = ctx.subject_codes
    try:
        ...  # existing business logic unchanged
        return ToolResult(success=True, data={"exams": [...]})
    except Exception as e:
        return ToolResult(success=False, error=str(e))
```

Add `from edu_cloud.ai.tool_context import ToolContext, ToolResult` at the top.

- [ ] **Step 2: Update tests**

Adapt test calls from `await tools.execute("get_exam_list", {"status": "draft"}, _db=db, _school_id=sid)` to:
```python
ctx = ToolContext(db=db, school_id=sid, user_id="U1", role="admin")
result = await tools.execute("get_exam_list", {"status": "draft"}, ctx)
assert result.success is True
```

- [ ] **Step 3: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_tools_exams.py -v`

- [ ] **Step 4: Commit**

```bash
git commit -m "refactor(agent): migrate exam tools to ToolContext/ToolResult interface"
```

---

### Task 16-25: Migrate remaining tool files (same pattern)

Each tool file follows the identical mechanical transformation from Task 15. One commit per tool file:

| Task | File | Tools | Sensitivity |
|------|------|-------|------------|
| 16 | tools/analytics.py | get_exam_scores, get_class_stats | school |
| 17 | tools/analytics_score.py | get_exam_summary + 4 more | school |
| 18 | tools/analytics_compare.py | compare_classes + 2 more | school |
| 19 | tools/students.py | get_class_list + 3 more | student |
| 20 | tools/knowledge.py | search_curriculum + 3 more | public |
| 21 | tools/knowledge_db.py | get_knowledge_tree + 1 more | school |
| 22 | tools/homework.py | list_homework_tasks + 4 more | school (read) / school (write) |
| 23 | tools/grading_ops.py | get_grading_progress + 2 more | school |
| 24 | tools/bank.py | get_student_error_book + 1 more | student |
| 25 | tools/profile.py | get_student_trend + 3 more | student |
| 26 | tools/actions.py | generate_report + 1 more | school |

For each task, steps are identical to Task 15:
1. Add `from edu_cloud.ai.tool_context import ToolContext, ToolResult` import
2. Change function signature to `(input: dict, ctx: ToolContext) -> ToolResult`
3. Extract parameters from `input` dict, context from `ctx`
4. Wrap return in `ToolResult(success=True, data=...)`
5. Add `try/except` wrapping to `ToolResult(success=False, error=...)`
6. Add `is_read_only` and `sensitivity` to `@tools.register()`
7. Update corresponding test file
8. Run tests, commit

---

## Batch 7: Integration + Cleanup

### Task 27: Wire AgentLoop into API endpoint

**Files:**
- Modify: `src/edu_cloud/api/ai.py`
- Test: `tests/test_ai/test_ai_api.py` (extend existing)

- [ ] **Step 1: Replace old Agent with AgentLoop in POST /chat endpoint**

The endpoint's pipeline stages change from:
```
IntentResolver → ModelRouter → create_llm_for_tier → Agent.run()
```
To:
```
CapabilityProbe.get_tier() → ToolAccessResolver → SensitivityRouter → AgentLoop.run()
```

- [ ] **Step 2: Write entry-level SSE contract tests (F003)**

> Task 14 验证了 AgentEvent 序列化和 AgentLoop 事件产出，但未经过 HTTP 入口。本步骤补充入口级 SSE 验证。

Add tests to `tests/test_ai/test_ai_api.py` that use AsyncClient POST to `/api/v1/ai/chat` and verify:
- SSE 流包含 answer + done 事件
- 旧事件类型格式不变 (INV-004)
- 新事件类型 (thinking/plan/task_update) 通过 SSE 正确传输

- [ ] **Step 3: Run full test suite**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(agent): wire AgentLoop into /api/v1/ai/chat endpoint"
```

**测试契约:**
1. POST /api/v1/ai/chat 返回 SSE 流，包含 answer + done 事件
   - 入口: `AsyncClient.post("/api/v1/ai/chat", json={...})`
   - 反例: 如果 wiring 遗漏 AgentLoop.run()，返回旧 Agent 格式而非 AgentEvent SSE
   - 边界: 空消息 / 无权限用户 / session 不存在
   - 回归: 旧 answer/tool_call/tool_result/done 格式不变
   - 命令: `pytest tests/test_ai/test_ai_api.py -v -k agent_loop`

**边界条件:**
- 空消息体 → 期望: 400 错误
- 无 JWT token → 期望: 401
- LLM 返回空响应 → 期望: SSE 流中含 error + done 事件

---

### Task 28: Delete deprecated files (with rollback checkpoint)

**Files:**
- Delete: `src/edu_cloud/ai/agent.py`
- Delete: `src/edu_cloud/ai/llm.py`
- Delete: `src/edu_cloud/ai/llm_factory.py`
- Delete: `src/edu_cloud/ai/model_router.py`
- Delete: `src/edu_cloud/ai/intent_resolver.py`
- Delete: `src/edu_cloud/ai/context.py`

- [ ] **Step 1: Create rollback checkpoint**

```bash
cd C:/Users/Administrator/edu-cloud
git tag edu-agent-pre-cutover
```

- [ ] **Step 2: Run full test suite to confirm new+old coexistence is green**

```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q
```

Expected: All tests PASS before any deletion. This is the "safe baseline".

- [ ] **Step 3: Delete deprecated files and remove old test files**

```bash
cd C:/Users/Administrator/edu-cloud
git rm src/edu_cloud/ai/agent.py src/edu_cloud/ai/llm.py src/edu_cloud/ai/llm_factory.py \
       src/edu_cloud/ai/model_router.py src/edu_cloud/ai/intent_resolver.py src/edu_cloud/ai/context.py
```

- [ ] **Step 4: Run full test suite to confirm nothing breaks**

```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q
```

Expected: All tests PASS. If any test fails due to imports from deleted files, fix the import or remove the test.

**Rollback procedure:** If Step 4 fails and fixes are non-trivial:
```bash
git checkout edu-agent-pre-cutover -- src/edu_cloud/ai/agent.py src/edu_cloud/ai/llm.py \
    src/edu_cloud/ai/llm_factory.py src/edu_cloud/ai/model_router.py \
    src/edu_cloud/ai/intent_resolver.py src/edu_cloud/ai/context.py
```
Then investigate which module still depends on the old files before retrying.

- [ ] **Step 5: Commit**

```bash
git commit -m "chore(agent): remove deprecated AI module files replaced by edu-agent"
```

**测试契约:**
1. 删除旧文件后全量测试仍绿
   - 入口: `python -m pytest --tb=short -q`
   - 反例: 如果有遗漏的 import 引用旧文件，测试会 ImportError
   - 边界: grep 旧模块名确认零残留
   - 回归: N/A
   - 命令: `python -m pytest --tb=short -q`

**边界条件:**
- grep "from edu_cloud.ai.agent import" → 期望: 零结果
- grep "from edu_cloud.ai.llm import" → 期望: 零结果
- grep "from edu_cloud.ai.intent_resolver import" → 期望: 零结果

---

### Task 29: Verify Alembic migration head + downgrade

> Migration file was created in Task 10. This task verifies the migration chain integrity after all code changes.

- [ ] **Step 1: Verify migration head is consistent**

```bash
cd C:/Users/Administrator/edu-cloud
python -m alembic heads
python -m alembic check
```

Expected: single head, no drift.

- [ ] **Step 2: Run full migration smoke test (upgrade + downgrade)**

```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_alembic_migration.py -v
```

Expected: PASS — all tables (including agent_memories) present after upgrade, clean after downgrade.

- [ ] **Step 3: Commit** (only if smoke test revealed fixes needed)

```bash
git commit -m "test(agent): verify Alembic migration head integrity after edu-agent integration"
```

**测试契约:**
1. Alembic head 包含 agent_memories 表
   - 入口: `python -m alembic upgrade head && python -m alembic downgrade -1 && python -m alembic upgrade head`
   - 反例: 如果 env.py 未导入 AgentMemory，autogenerate 不发现表，upgrade 后表不存在
   - 边界: upgrade/downgrade 循环 / 空数据库
   - 回归: N/A
   - 命令: `pytest tests/test_alembic_migration.py -v`

**边界条件:**
- 空数据库 upgrade → 期望: 所有表创建成功（含 agent_memories）
- upgrade 后 downgrade → 期望: agent_memories 表删除，其他表保留
- 重复 upgrade → 期望: 幂等，无报错

---

### Task 30: Final integration test

- [ ] **Step 1: Run full test suite**

```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q
```

All tests must pass.

- [ ] **Step 2: Verify tool count**

```bash
cd C:/Users/Administrator/edu-cloud && python -c "from edu_cloud.ai.registry import tools; print(f'{len(tools.list_tools())} tools registered')"
```

Expected: `39 tools registered`

- [ ] **Step 3: Final commit**

```bash
git commit -m "test(agent): verify edu-agent integration — all tests green, 39 tools registered"
```

---

## Summary

| Batch | Tasks | Description | Est. LOC |
|-------|-------|-------------|----------|
| 1 | 1-4 | Foundation (ToolContext, Registry, Access, Schemas) | ~350 |
| 2 | 5-7 | LLM Adapter + CapabilityProbe + SensitivityRouter | ~400 |
| 3 | 8 | ToolExecutor + ToolOrchestrator | ~200 |
| 4 | 9-11 | ContextManager + SessionMemory + TaskPlanner | ~450 |
| 5 | 12-14 | AgentLoop + Prompts + API tests | ~400 |
| 6 | 15-26 | 39 tool migration (12 files) | ~585 |
| 7 | 27-30 | Integration + cleanup + migration | ~100 |
| **Total** | **30** | | **~2,485** |
