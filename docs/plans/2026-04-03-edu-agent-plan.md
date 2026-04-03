# edu-agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace edu-cloud's existing ReAct agent with a Claude Code-inspired multi-tier agent kernel that supports planning, parallel tool execution, context compression, session memory, and dual-channel LLM routing.

**Architecture:** Bottom-up build in 7 batches. Each batch produces testable, committable code. Foundation layer first (data structures + registry), then LLM adapter, tool execution pipeline, intelligence layer (planning + memory), and finally the agent loop that wires everything together. Last batch migrates all 39 existing tools to the new interface.

**Tech Stack:** Python 3.11+ / asyncio / FastAPI / SQLAlchemy async / httpx / Pydantic

**Design Doc:** `docs/plans/2026-04-03-edu-agent-design.md`

---

## Batch 1: Foundation Layer

> ToolContext, ToolResult, ToolSpec, ToolRegistry, ToolAccessResolver, AgentEvent schemas.
> Everything else depends on this batch.

### Task 1: ToolContext and ToolResult data structures

**Files:**
- Create: `src/edu_cloud/ai/tool_context.py`
- Test: `tests/test_tool_context.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_tool_context.py
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

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_tool_context.py -v`
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

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_tool_context.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/ai/tool_context.py tests/test_tool_context.py
git commit -m "feat(agent): add ToolContext and ToolResult data structures"
```

---

### Task 2: Refactor ToolSpec and ToolRegistry

**Files:**
- Modify: `src/edu_cloud/ai/registry.py`
- Modify: `tests/test_registry.py`

- [ ] **Step 1: Write failing tests for new ToolSpec fields and new register signature**

```python
# tests/test_registry_v2.py
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

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_registry_v2.py -v`
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

    async def execute(self, name: str, arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
        spec = self._tools.get(name)
        if spec is None:
            return ToolResult(success=False, error=f"Unknown tool: {name}")
        try:
            result = spec.func(arguments, ctx)
            if inspect.isawaitable(result):
                result = await result
            return result
        except Exception as exc:
            logger.exception("Tool %s execution failed", name)
            return ToolResult(success=False, error=str(exc))


# Global registry instance
tools = ToolRegistry()
```

- [ ] **Step 4: Run new tests + existing registry tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_registry_v2.py tests/test_registry.py -v`
Expected: test_registry_v2.py all PASS. test_registry.py will FAIL (old execute() signature uses **kwargs instead of ToolContext). That's expected — old tests will be updated in Batch 6 along with tool migration.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/ai/registry.py tests/test_registry_v2.py
git commit -m "feat(agent): refactor ToolSpec with is_read_only + sensitivity, ToolRegistry new execute()"
```

---

### Task 3: Refactor ToolAccessResolver

**Files:**
- Modify: `src/edu_cloud/ai/tool_access.py`
- Create: `tests/test_tool_access_v2.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_tool_access_v2.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_tool_access_v2.py -v`
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
        return all(caps.get(req, False) for req in required)
```

- [ ] **Step 4: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_tool_access_v2.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/ai/tool_access.py tests/test_tool_access_v2.py
git commit -m "feat(agent): refactor ToolAccessResolver to sync three-layer filter"
```

---

### Task 4: Extend AgentEvent schemas

**Files:**
- Modify: `src/edu_cloud/ai/schemas.py`
- Create: `tests/test_schemas_v2.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_schemas_v2.py
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

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_schemas_v2.py -v`
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

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_schemas_v2.py tests/test_schemas.py -v 2>/dev/null; python -m pytest tests/test_schemas_v2.py -v`
Expected: test_schemas_v2.py all PASS. Old tests may need minor adaptation (ChatMessage alias keeps them working).

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/ai/schemas.py tests/test_schemas_v2.py
git commit -m "feat(agent): extend schemas with Message, Transition enum, new AgentEvent types"
```

---

## Batch 2: LLM Adapter Layer

> LLMAdapter protocol, LLMProxyAdapter, CapabilityProbe, SensitivityRouter.

### Task 5: LLM Adapter protocol and LLMProxyAdapter

**Files:**
- Create: `src/edu_cloud/ai/llm_adapter.py`
- Test: `tests/test_llm_adapter.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_llm_adapter.py
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

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_llm_adapter.py -v`
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

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_llm_adapter.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/ai/llm_adapter.py tests/test_llm_adapter.py
git commit -m "feat(agent): add LLMProxyAdapter with OpenAI-compatible llm-proxy integration"
```

---

### Task 6: CapabilityProbe

**Files:**
- Create: `src/edu_cloud/ai/capability_probe.py`
- Test: `tests/test_capability_probe.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_capability_probe.py
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

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_capability_probe.py -v`
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

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_capability_probe.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/ai/capability_probe.py tests/test_capability_probe.py
git commit -m "feat(agent): add CapabilityProbe with auto tier detection + manual override"
```

---

### Task 7: SensitivityRouter

**Files:**
- Create: `src/edu_cloud/ai/sensitivity_router.py`
- Test: `tests/test_sensitivity_router.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_sensitivity_router.py
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

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_sensitivity_router.py -v`
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

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_sensitivity_router.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/ai/sensitivity_router.py tests/test_sensitivity_router.py
git commit -m "feat(agent): add SensitivityRouter with dual-channel data protection"
```

---

## Batch 3: Tool Execution Pipeline

> ToolExecutor + ToolOrchestrator — the engine that runs tools with permission checks, error handling, and concurrent/serial batching.

### Task 8: ToolExecutor and ToolOrchestrator

**Files:**
- Create: `src/edu_cloud/ai/tool_executor.py`
- Test: `tests/test_tool_executor.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_tool_executor.py
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

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_tool_executor.py -v`
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

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_tool_executor.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/ai/tool_executor.py tests/test_tool_executor.py
git commit -m "feat(agent): add ToolExecutor + ToolOrchestrator with concurrent batching"
```

---

## Batch 4: Intelligence Layer

> ContextManager (compression + token counting), SessionMemoryExtractor, AgentMemory model, TaskPlanner.

### Task 9: ContextManager

**Files:**
- Create: `src/edu_cloud/ai/context_manager.py`
- Test: `tests/test_context_manager.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_context_manager.py
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

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_context_manager.py -v`
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

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_context_manager.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/ai/context_manager.py tests/test_context_manager.py
git commit -m "feat(agent): add ContextManager with auto-compact and token estimation"
```

---

### Task 10: AgentMemory model + SessionMemoryExtractor

**Files:**
- Create: `src/edu_cloud/models/agent_memory.py`
- Create: `src/edu_cloud/ai/session_memory.py`
- Test: `tests/test_session_memory.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_session_memory.py
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

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_session_memory.py -v`
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

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_session_memory.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/models/agent_memory.py src/edu_cloud/ai/session_memory.py tests/test_session_memory.py
git commit -m "feat(agent): add AgentMemory model + SessionMemoryExtractor"
```

---

### Task 11: TaskPlanner

**Files:**
- Create: `src/edu_cloud/ai/task_planner.py`
- Test: `tests/test_task_planner.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_task_planner.py
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

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_task_planner.py -v`
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

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_task_planner.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/ai/task_planner.py tests/test_task_planner.py
git commit -m "feat(agent): add TaskPlanner with LLM-driven decomposition and topological scheduling"
```

---

## Batch 5: Agent Loop + Prompts + API

> The core agent loop that wires everything together, system prompt templates, and API endpoint adaptation.

### Task 12: System prompt templates

**Files:**
- Create: `src/edu_cloud/ai/prompts.py`
- Test: `tests/test_prompts.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_prompts.py
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

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_prompts.py -v`
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

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_prompts.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/ai/prompts.py tests/test_prompts.py
git commit -m "feat(agent): add system prompt templates with tier-aware instructions"
```

---

### Task 13: AgentLoop — the core

**Files:**
- Create: `src/edu_cloud/ai/agent_loop.py`
- Test: `tests/test_agent_loop.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_agent_loop.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_agent_loop.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement agent_loop.py**

```python
# src/edu_cloud/ai/agent_loop.py
"""Core agent loop — plan, execute tools, verify, respond (Design §3).

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
    ):
        self._registry = registry
        self._adapter = adapter
        self._strategy = strategy
        self._orchestrator = ToolOrchestrator(registry)
        self._context_mgr = ContextManager()
        self._planner = TaskPlanner()

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

        while state.turn_count < self._strategy.max_turns:
            state.turn_count += 1

            # Check if compaction needed
            if self._strategy.context_compact and self._context_mgr.should_compact(
                state.token_count, self._adapter.context_window_size()
            ):
                state.messages = await self._context_mgr.compact(state.messages, self._adapter)
                state.token_count = TokenCounter.estimate_messages(state.messages)

            # Call LLM
            try:
                resp = await self._adapter.chat(LLMRequest(
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
            if resp.stop_reason == "end_turn" and resp.content:
                # Direct answer
                state.messages.append(Message(role="assistant", content=resp.content))
                yield AgentEvent(type="answer", data={"content": resp.content})
                break

            if resp.tool_calls:
                # Tool calls
                state.messages.append(Message(role="assistant", content=resp.content, tool_calls=resp.tool_calls))

                for tc in resp.tool_calls:
                    yield AgentEvent(type="tool_call", data={"tool": tc.name, "args": tc.arguments, "id": tc.id})

                # Execute tools
                batches = self._orchestrator.partition(resp.tool_calls)
                if not self._strategy.parallel_tools:
                    # Tier 3: flatten to serial
                    from edu_cloud.ai.tool_executor import ToolBatch
                    batches = [ToolBatch(calls=[c], concurrent=False) for c in resp.tool_calls]

                results = await self._orchestrator.execute(batches, ctx)

                # Add results to messages
                for tc, result in zip(resp.tool_calls, results):
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

            # No content and no tool calls — unexpected
            logger.warning("LLM returned empty response at turn %d", state.turn_count)
            break

        yield AgentEvent(type="done", data={
            "turns": state.turn_count,
            "tokens": state.token_count,
            "channel": state.channel,
        })
```

- [ ] **Step 4: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_agent_loop.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/ai/agent_loop.py tests/test_agent_loop.py
git commit -m "feat(agent): add AgentLoop core with tool execution and max_turns protection"
```

---

### Task 14: API endpoint adaptation

**Files:**
- Modify: `src/edu_cloud/api/ai.py`
- Test: `tests/test_ai_api_v2.py`

> This task adapts the existing `/api/v1/ai/chat` endpoint to use the new AgentLoop instead of the old Agent class. The SSE streaming format stays the same but supports new event types (plan, task_update, thinking).

- [ ] **Step 1: Write failing test**

```python
# tests/test_ai_api_v2.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from edu_cloud.ai.schemas import AgentEvent


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
        import json
        line = f"data: {json.dumps(d, ensure_ascii=False)}\n\n"
        assert event.type in line
```

- [ ] **Step 2: Run test to verify it passes** (this is a schema test, should pass with existing code)

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai_api_v2.py -v`
Expected: PASS

- [ ] **Step 3: Document the API migration plan**

The actual `api/ai.py` migration is deferred to Batch 7 (integration), because it requires all 39 tools to be migrated first. For now, the old Agent class and new AgentLoop coexist. The API endpoint will be updated last.

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add tests/test_ai_api_v2.py
git commit -m "test(agent): add API SSE serialization tests for new AgentEvent types"
```

---

## Batch 6: Tool Migration

> Migrate all 39 existing tools from the old `async def func(**kwargs)` signature to the new `async def func(input: dict, ctx: ToolContext) -> ToolResult` signature.

### Task 15: Migrate exam tools (3 tools)

**Files:**
- Modify: `src/edu_cloud/ai/tools/exams.py`
- Modify: `tests/test_tools_exams.py` (adapt tests)

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

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_tools_exams.py -v`

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

- [ ] **Step 1: Replace old Agent with AgentLoop in POST /chat endpoint**

The endpoint's pipeline stages change from:
```
IntentResolver → ModelRouter → create_llm_for_tier → Agent.run()
```
To:
```
CapabilityProbe.get_tier() → ToolAccessResolver → SensitivityRouter → AgentLoop.run()
```

- [ ] **Step 2: Run full test suite**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(agent): wire AgentLoop into /api/v1/ai/chat endpoint"
```

---

### Task 28: Delete deprecated files

**Files:**
- Delete: `src/edu_cloud/ai/agent.py`
- Delete: `src/edu_cloud/ai/llm.py`
- Delete: `src/edu_cloud/ai/llm_factory.py`
- Delete: `src/edu_cloud/ai/model_router.py`
- Delete: `src/edu_cloud/ai/intent_resolver.py`
- Delete: `src/edu_cloud/ai/context.py`

- [ ] **Step 1: Delete files and remove old test files**

- [ ] **Step 2: Run full test suite to confirm nothing breaks**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`

- [ ] **Step 3: Commit**

```bash
git commit -m "chore(agent): remove deprecated AI module files replaced by edu-agent"
```

---

### Task 29: Alembic migration for agent_memories table

**Files:**
- Create: `alembic/versions/xxx_add_agent_memories.py`

- [ ] **Step 1: Generate migration**

```bash
cd C:/Users/Administrator/edu-cloud
python -m alembic revision --autogenerate -m "add agent_memories table"
```

- [ ] **Step 2: Run migration**

```bash
python -m alembic upgrade head
```

- [ ] **Step 3: Commit**

```bash
git commit -m "migration: add agent_memories table for session memory persistence"
```

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
