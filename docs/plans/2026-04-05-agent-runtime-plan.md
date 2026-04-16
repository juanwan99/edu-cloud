# Agent Runtime 架构升级 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Agent 从 HTTP 请求附属品升级为独立运行时，支持多入口（HTTP/Worker/CLI）、双层模型路由、防幻觉三层防线。

**Architecture:** AgentRuntime 统一调度器从 api/ai.py 提取编排逻辑；ModelRouter 按规则路由主力/增强模型；OutputValidator 后置校验数据类回复；Worker/CLI 复用同一 AgentRuntime。

**Tech Stack:** FastAPI + arq + existing Supervisor/AgentLoop/Tools + 现有 LLMProxyAdapter

**Design doc:** `docs/plans/2026-04-05-agent-runtime-design.md`

**依赖:** Phase 1 多 Agent 编排 + Phase 2 跨会话记忆（均已完成）

---

## 文件结构

| 文件 | 类型 | 职责 |
|------|------|------|
| `src/edu_cloud/ai/runtime.py` | 新增 | AgentRuntime + AgentContext |
| `src/edu_cloud/ai/model_router.py` | 新增 | ModelRouter 双层模型路由 |
| `src/edu_cloud/ai/grounded.py` | 新增 | DataSource + OutputValidator |
| `src/edu_cloud/ai/tool_context.py` | 修改 | ToolResult 加 source 字段 |
| `src/edu_cloud/ai/agent_loop.py` | 修改 | answer 事件前调 OutputValidator |
| `src/edu_cloud/ai/prompts.py` | 修改 | 加 Grounded 数据引用规则 |
| `src/edu_cloud/api/ai.py` | 修改 | 瘦身为 HTTP 胶水，调 AgentRuntime |
| `src/edu_cloud/worker.py` | 修改 | 注册 run_agent_scheduled |
| `src/edu_cloud/core/events.py` | 修改 | exam.published → Agent 入队 |
| `src/edu_cloud/cli/__init__.py` | 新增 | 空包 |
| `src/edu_cloud/cli/agent.py` | 新增 | CLI 入口 |
| `tests/test_ai/test_runtime.py` | 新增 | Runtime 测试 |
| `tests/test_ai/test_model_router.py` | 新增 | 路由测试 |
| `tests/test_ai/test_grounded.py` | 新增 | 校验测试 |
| `tests/test_ai/test_agent_cli.py` | 新增 | CLI 测试 |

> **Note:** 设计文档路径为 `memory_tools.py`（§5 F007 确认）。

---

### Task 1: DataSource + ToolResult.source 扩展

**Files:**
- Create: `src/edu_cloud/ai/grounded.py`（DataSource 定义部分）
- Modify: `src/edu_cloud/ai/tool_context.py`
- Test: `tests/test_ai/test_grounded.py`

**测试契约:**
1. ToolResult 接受 source 参数
   - 入口: `ToolResult(success=True, data={"avg": 72}, source=DataSource(...))`
   - 反例: 错误实现忽略 source 参数导致序列化丢失
   - 边界: source=None（默认）/ source 完整 / to_dict() 包含 source
   - 回归: 现有 ToolResult 用法不受影响
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_grounded.py::TestDataSource -v`

**审查清单:**
- ✓ DataSource 是 frozen dataclass
- ✓ ToolResult.source 默认 None（向后兼容）
- ✓ to_dict() 包含 source（非 None 时）
- ✗ 不修改现有 42 个工具（逐步迁移，不阻塞）

**边界条件:**
- source=None → to_dict() 不含 source key
- source 完整 → to_dict() 含 source dict
- 现有代码传 ToolResult 不传 source → 正常工作

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_grounded.py
import pytest
from edu_cloud.ai.grounded import DataSource
from edu_cloud.ai.tool_context import ToolResult


class TestDataSource:
    def test_create(self):
        ds = DataSource(type="db_query", table="exam_scores", ref="2026期中", queried_at="2026-04-05T20:30:00")
        assert ds.type == "db_query"
        assert ds.table == "exam_scores"

    def test_frozen(self):
        ds = DataSource(type="db_query", table="t", ref="r", queried_at="now")
        with pytest.raises(AttributeError):
            ds.type = "other"

    def test_to_dict(self):
        ds = DataSource(type="db_query", table="exam_scores", ref="期中", queried_at="2026-04-05T20:30:00")
        d = ds.to_dict()
        assert d["type"] == "db_query"
        assert d["table"] == "exam_scores"


class TestToolResultSource:
    def test_source_default_none(self):
        r = ToolResult(success=True, data={"avg": 72})
        assert r.source is None

    def test_source_with_data(self):
        ds = DataSource(type="db_query", table="exam_scores", ref="期中", queried_at="now")
        r = ToolResult(success=True, data={"avg": 72}, source=ds)
        assert r.source.type == "db_query"

    def test_to_dict_without_source(self):
        r = ToolResult(success=True, data={"avg": 72})
        d = r.to_dict()
        assert "source" not in d

    def test_to_dict_with_source(self):
        ds = DataSource(type="db_query", table="exam_scores", ref="期中", queried_at="now")
        r = ToolResult(success=True, data={"avg": 72}, source=ds)
        d = r.to_dict()
        assert d["source"]["type"] == "db_query"

    def test_backward_compat_existing_usage(self):
        """Existing code creates ToolResult without source — must still work."""
        r = ToolResult(success=True, data=[{"id": "1"}])
        assert r.success
        r2 = ToolResult(success=False, error="fail")
        assert r2.error == "fail"
```

- [ ] **Step 2: Run tests — should FAIL**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_grounded.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement DataSource**

```python
# src/edu_cloud/ai/grounded.py
"""Grounded Generation: DataSource tagging + OutputValidator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DataSource:
    """Origin tag for tool-returned data."""
    type: str       # "db_query" | "api_call" | "computed"
    table: str | None
    ref: str | None      # human-readable reference (exam name, date)
    queried_at: str      # ISO timestamp

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in {
            "type": self.type,
            "table": self.table,
            "ref": self.ref,
            "queried_at": self.queried_at,
        }.items() if v is not None}
```

- [ ] **Step 4: Modify ToolResult — add source field**

In `src/edu_cloud/ai/tool_context.py`, add import and field:

```python
from edu_cloud.ai.grounded import DataSource
```

Add to ToolResult dataclass:
```python
    source: DataSource | None = None
```

Update `to_dict()` to include source when present:
```python
    def to_dict(self) -> dict:
        d: dict[str, Any] = {"success": self.success, "data": self.data}
        if self.error is not None:
            d["error"] = self.error
        if self.metadata is not None:
            d["metadata"] = self.metadata
        if self.source is not None:
            d["source"] = self.source.to_dict()
        return d
```

- [ ] **Step 5: Run tests — should PASS**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_grounded.py -v`
Expected: All 8 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/ai/grounded.py src/edu_cloud/ai/tool_context.py tests/test_ai/test_grounded.py
git commit -m "feat(runtime): add DataSource + ToolResult.source field"
```

---

### Task 2: OutputValidator（防幻觉后置校验）

**Files:**
- Modify: `src/edu_cloud/ai/grounded.py`（追加 OutputValidator）
- Test: `tests/test_ai/test_grounded.py`（追加）

**测试契约:**
1. 数值一致时 PASS
   - 入口: `validator.validate("平均分 72.3 分", [ToolResult(data={"avg": 72.3})])`
   - 反例: 错误实现总返回 pass 不做校验
   - 边界: 无数值回复 / 无工具调用 / 数值完全匹配
   - 回归: N/A
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_grounded.py::TestOutputValidator -v`
2. 数值矛盾时 FAIL
   - 入口: `validator.validate("平均分 85 分", [ToolResult(data={"avg": 72.3})])`
   - 反例: 错误实现不比对数值
   - 边界: 整数 vs 浮点 / 百分比 / 中文数字
   - 回归: N/A
   - 命令: 同上

**审查清单:**
- ✓ 纯正则 + 数值比对，不调 LLM
- ✓ 无工具调用时跳过（返回 pass）
- ✓ 提取中文数值模式（xx分/xx%/xx人/xx名）
- ✗ 不处理模糊表述（"约七十分"→ 不提取）

**边界条件:**
- 纯闲聊无数值 → pass
- 工具返回但回复未提及数值 → pass
- 数值完全匹配 → pass
- 回复数值与工具数据矛盾 → fail
- 回复含未溯源数值（工具未返回）→ warn

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_grounded.py（追加到文件末尾）
from edu_cloud.ai.grounded import OutputValidator, ValidationResult


class TestOutputValidator:
    def setup_method(self):
        self.validator = OutputValidator()

    def test_no_tools_pass(self):
        """No tool calls → skip validation."""
        result = self.validator.validate("你好，有什么可以帮你的？", [])
        assert result.status == "pass"

    def test_no_numbers_pass(self):
        """Response has no numbers → pass."""
        tr = ToolResult(success=True, data={"avg": 72.3})
        result = self.validator.validate("成绩整体还不错", [tr])
        assert result.status == "pass"

    def test_matching_number_pass(self):
        """Response number matches tool data → pass."""
        tr = ToolResult(success=True, data={"avg": 72.3})
        result = self.validator.validate("班级平均分 72.3 分", [tr])
        assert result.status == "pass"

    def test_matching_percentage_pass(self):
        tr = ToolResult(success=True, data={"excellent_rate": 0.38})
        result = self.validator.validate("优秀率 38%", [tr])
        assert result.status == "pass"

    def test_contradicting_number_fail(self):
        """Response number contradicts tool data → fail."""
        tr = ToolResult(success=True, data={"avg": 72.3})
        result = self.validator.validate("班级平均分 85 分", [tr])
        assert result.status == "fail"

    def test_ungrounded_number_warn(self):
        """Response contains number not in any tool result → warn."""
        tr = ToolResult(success=True, data={"avg": 72.3})
        result = self.validator.validate("班级平均分 72.3 分，最高分 98 分", [tr])
        assert result.status == "warn"
        assert 98.0 in result.ungrounded_values

    def test_integer_float_match(self):
        """72 should match 72.0."""
        tr = ToolResult(success=True, data={"count": 72})
        result = self.validator.validate("共 72 人", [tr])
        assert result.status == "pass"

    def test_nested_data(self):
        """Validator should flatten nested dicts."""
        tr = ToolResult(success=True, data={"stats": {"avg": 72.3, "max": 98}})
        result = self.validator.validate("平均 72.3 分，最高 98 分", [tr])
        assert result.status == "pass"
```

- [ ] **Step 2: Run tests — should FAIL**

- [ ] **Step 3: Implement OutputValidator**

```python
# src/edu_cloud/ai/grounded.py（追加）
import re

@dataclass
class ValidationResult:
    status: str  # "pass" | "warn" | "fail"
    ungrounded_values: list[float] = field(default_factory=list)
    contradictions: list[dict] = field(default_factory=list)

# 中文数值提取模式
_NUM_PATTERN = re.compile(
    r'(\d+\.?\d*)\s*(?:分|%|人|名|个|次|所|班|科|题|道)'
)
_PERCENT_PATTERN = re.compile(r'(\d+\.?\d*)\s*%')


class OutputValidator:
    """Post-generation validator: check response numbers against tool data."""

    def validate(self, response: str, tool_results: list) -> ValidationResult:
        if not tool_results:
            return ValidationResult(status="pass")

        # Extract numbers from response
        response_nums = self._extract_numbers(response)
        if not response_nums:
            return ValidationResult(status="pass")

        # Collect all numbers from tool results
        tool_nums = set()
        for tr in tool_results:
            if tr.data:
                self._collect_numbers(tr.data, tool_nums)

        if not tool_nums:
            return ValidationResult(status="pass")

        # Compare
        ungrounded = []
        contradictions = []
        for num in response_nums:
            if self._matches_any(num, tool_nums):
                continue  # grounded
            # Check if it contradicts (close to a tool number but wrong)
            closest = self._find_closest(num, tool_nums)
            if closest is not None and abs(num - closest) / max(abs(closest), 1) < 0.5:
                contradictions.append({"response": num, "tool": closest})
            else:
                ungrounded.append(num)

        if contradictions:
            return ValidationResult(status="fail", contradictions=contradictions)
        if ungrounded:
            return ValidationResult(status="warn", ungrounded_values=ungrounded)
        return ValidationResult(status="pass")

    def _extract_numbers(self, text: str) -> list[float]:
        nums = []
        for m in _NUM_PATTERN.finditer(text):
            nums.append(float(m.group(1)))
        return list(set(nums))

    def _collect_numbers(self, data, result: set, depth: int = 0):
        if depth > 5:
            return
        if isinstance(data, (int, float)):
            result.add(float(data))
            # Also add percentage form (0.38 → 38.0)
            if 0 < data < 1:
                result.add(round(data * 100, 2))
        elif isinstance(data, dict):
            for v in data.values():
                self._collect_numbers(v, result, depth + 1)
        elif isinstance(data, list):
            for item in data:
                self._collect_numbers(item, result, depth + 1)

    def _matches_any(self, num: float, tool_nums: set[float]) -> bool:
        for tn in tool_nums:
            if abs(num - tn) < 0.01:  # tolerance for float comparison
                return True
        return False

    def _find_closest(self, num: float, tool_nums: set[float]) -> float | None:
        if not tool_nums:
            return None
        return min(tool_nums, key=lambda x: abs(x - num))
```

- [ ] **Step 4: Run tests — should PASS**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_grounded.py -v`
Expected: All 16 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/ai/grounded.py tests/test_ai/test_grounded.py
git commit -m "feat(runtime): add OutputValidator — grounded generation post-check"
```

---

### Task 3: ModelRouter（双层模型路由）

**Files:**
- Create: `src/edu_cloud/ai/model_router.py`
- Test: `tests/test_ai/test_model_router.py`

**测试契约:**
1. 增强未开通 → 主力模型
   - 入口: `router.route("分析成绩", context)` where `context.enhanced_enabled=False`
   - 反例: 错误实现忽略 enhanced_enabled 标志
   - 边界: user_slots 为空 / system_slots 为空
   - 回归: N/A
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_model_router.py -v`
2. 增强已开通 + 简单查询 → 主力模型
   - 入口: `router.route("张三的数学成绩", context)` where `enhanced_enabled=True`
   - 反例: 错误实现所有请求都走增强
   - 边界: 空消息 / 单字消息
   - 回归: N/A
   - 命令: 同上
3. 增强已开通 + 复杂分析 → 增强模型
   - 入口: `router.route("分析全校数学成绩趋势并生成报告", context)` where `enhanced_enabled=True`
   - 反例: 错误实现不检测关键词
   - 边界: 关键词在消息末尾 / 多个关键词
   - 回归: N/A
   - 命令: 同上

**审查清单:**
- ✓ 路由判断零 token 消耗（纯规则）
- ✓ enhanced_enabled=False 时必返主力
- ✓ system_slots 为空时降级到主力
- ✗ 不调 LLM 做复杂度判断

**边界条件:**
- user_slots=[] 且 system_slots=[] → 抛异常（无可用模型）
- enhanced_enabled=True 但 system_slots=[] → 走主力（安全降级）
- 空消息 → 走主力

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_model_router.py
import pytest
from dataclasses import dataclass
from edu_cloud.ai.model_router import ModelRouter, ModelChoice


@dataclass
class MockSlot:
    slot_number: int
    api_url: str = "http://test"
    model: str = "test-model"


class TestModelRouter:
    def setup_method(self):
        self.router = ModelRouter()
        self.user_slots = [MockSlot(slot_number=1, model="deepseek-v3")]
        self.system_slots = [MockSlot(slot_number=99, model="claude-sonnet")]

    def test_enhanced_disabled_uses_user(self):
        choice = self.router.route(
            "分析成绩", self.user_slots, self.system_slots, enhanced_enabled=False
        )
        assert choice.tier == "standard"
        assert choice.slots == self.user_slots

    def test_simple_query_uses_user(self):
        choice = self.router.route(
            "张三的数学成绩是多少", self.user_slots, self.system_slots, enhanced_enabled=True
        )
        assert choice.tier == "standard"

    def test_complex_analysis_uses_system(self):
        choice = self.router.route(
            "分析全校数学成绩趋势并生成报告", self.user_slots, self.system_slots, enhanced_enabled=True
        )
        assert choice.tier == "advanced"

    def test_report_keyword_triggers_enhanced(self):
        choice = self.router.route(
            "帮我生成三年级数学诊断报告", self.user_slots, self.system_slots, enhanced_enabled=True
        )
        assert choice.tier == "advanced"

    def test_empty_system_slots_fallback(self):
        """Enhanced enabled but no system slots → fallback to user."""
        choice = self.router.route(
            "分析成绩趋势", self.user_slots, [], enhanced_enabled=True
        )
        assert choice.tier == "standard"
        assert choice.slots == self.user_slots

    def test_no_slots_raises(self):
        with pytest.raises(ValueError, match="无可用模型"):
            self.router.route("test", [], [], enhanced_enabled=False)

    def test_empty_message_uses_user(self):
        choice = self.router.route(
            "", self.user_slots, self.system_slots, enhanced_enabled=True
        )
        assert choice.tier == "standard"

    def test_multiple_keywords(self):
        choice = self.router.route(
            "对比各班成绩趋势", self.user_slots, self.system_slots, enhanced_enabled=True
        )
        assert choice.tier == "advanced"
```

- [ ] **Step 2: Run tests — should FAIL**

- [ ] **Step 3: Implement ModelRouter**

```python
# src/edu_cloud/ai/model_router.py
"""ModelRouter: zero-token rule-based model selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ModelChoice:
    slots: list[Any]
    tier: str  # "standard" | "advanced"


# Keywords that trigger enhanced model
_ENHANCE_KEYWORDS = [
    "分析", "报告", "对比", "趋势", "诊断", "评估",
    "预测", "建议", "规划", "总结", "深度",
]


class ModelRouter:
    """Select user (standard) vs system (advanced) model by keyword rules."""

    def route(
        self,
        message: str,
        user_slots: list[Any],
        system_slots: list[Any],
        enhanced_enabled: bool = False,
    ) -> ModelChoice:
        if not user_slots and not system_slots:
            raise ValueError("无可用模型")

        # Enhanced not enabled or not available → user model
        if not enhanced_enabled or not system_slots:
            return ModelChoice(slots=user_slots or system_slots, tier="standard")

        # Check if message triggers enhancement
        if self._needs_enhancement(message):
            return ModelChoice(slots=system_slots, tier="advanced")

        return ModelChoice(slots=user_slots, tier="standard")

    def _needs_enhancement(self, message: str) -> bool:
        if not message:
            return False
        return any(kw in message for kw in _ENHANCE_KEYWORDS)
```

- [ ] **Step 4: Run tests — should PASS**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_model_router.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/ai/model_router.py tests/test_ai/test_model_router.py
git commit -m "feat(runtime): add ModelRouter — zero-token dual-model routing"
```

---

### Task 4: AgentRuntime + AgentContext

**Files:**
- Create: `src/edu_cloud/ai/runtime.py`
- Test: `tests/test_ai/test_runtime.py`

**测试契约:**
1. AgentRuntime.run() 产出 AgentEvent 流
   - 入口: `async for event in runtime.run(message, context): ...`
   - 反例: 错误实现不 yield 任何事件
   - 边界: 空消息 / Supervisor 抛异常
   - 回归: N/A
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_runtime.py -v`
2. 模型路由集成
   - 入口: `runtime.run("分析成绩趋势", context_with_enhanced)`
   - 反例: 错误实现不调 ModelRouter
   - 边界: enhanced_enabled=False / system_slots 为空
   - 回归: N/A
   - 命令: 同上

**审查清单:**
- ✓ AgentContext 是 frozen dataclass
- ✓ AgentRuntime 无状态（每次 run() 独立）
- ✓ Supervisor/AgentLoop 不修改
- ✓ 向后兼容（api/ai.py 可渐进迁移）
- ✗ 不在 runtime 中处理 HTTP 概念

**边界条件:**
- enhanced_enabled=False → ModelRouter 返回 standard
- memory 加载失败 → 继续执行（graceful）
- OutputValidator fail → 重新生成（本 Task 只 yield 原始 event，Task 5 接入 validator）

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_runtime.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, field

from edu_cloud.ai.runtime import AgentRuntime, AgentContext


@dataclass(frozen=True)
class MockDataScope:
    visible_class_ids: list[str] | None = None
    visible_student_ids: list[str] | None = None


class TestAgentContext:
    def test_create(self):
        ctx = AgentContext(
            db=MagicMock(),
            user_id="u1",
            school_id="sch1",
            role="subject_teacher",
            data_scope=MockDataScope(),
            session_id="sess1",
            user_slots=[],
            system_slots=[],
            enhanced_enabled=False,
        )
        assert ctx.school_id == "sch1"
        assert not ctx.enhanced_enabled

    def test_frozen(self):
        ctx = AgentContext(
            db=MagicMock(), user_id="u1", school_id="sch1",
            role="teacher", data_scope=MockDataScope(),
            session_id="s1", user_slots=[], system_slots=[],
            enhanced_enabled=False,
        )
        with pytest.raises(AttributeError):
            ctx.school_id = "other"


class TestAgentRuntime:
    @pytest.mark.asyncio
    async def test_run_yields_events(self):
        """Runtime should yield events from Supervisor."""
        from edu_cloud.ai.schemas import AgentEvent

        mock_event = AgentEvent(type="answer", data={"content": "回答"})
        mock_done = AgentEvent(type="done", data={})

        with patch("edu_cloud.ai.runtime.Supervisor") as MockSup:
            instance = MockSup.return_value
            async def mock_handle(**kwargs):
                yield mock_event
                yield mock_done
            instance.handle = mock_handle

            with patch("edu_cloud.ai.runtime.CapabilityProbe") as MockProbe:
                MockProbe.return_value.determine_tier = AsyncMock(return_value=2)

                with patch("edu_cloud.ai.runtime.LLMProxyAdapter") as MockAdapter:
                    MockAdapter.return_value.context_window_size.return_value = 128000

                    runtime = AgentRuntime()
                    ctx = AgentContext(
                        db=MagicMock(), user_id="u1", school_id="sch1",
                        role="teacher", data_scope=MockDataScope(),
                        session_id="s1",
                        user_slots=[MagicMock(api_url="http://test", slot_number=1)],
                        system_slots=[], enhanced_enabled=False,
                    )

                    events = []
                    async for event in runtime.run("test", ctx):
                        events.append(event)

                    assert len(events) >= 1
                    assert any(e.type == "answer" for e in events)

    @pytest.mark.asyncio
    async def test_run_model_router_standard(self):
        """Enhanced disabled → standard model."""
        with patch("edu_cloud.ai.runtime.ModelRouter") as MockRouter:
            from edu_cloud.ai.model_router import ModelChoice
            MockRouter.return_value.route.return_value = ModelChoice(
                slots=[MagicMock()], tier="standard"
            )

            with patch("edu_cloud.ai.runtime.Supervisor") as MockSup:
                async def mock_handle(**kwargs):
                    from edu_cloud.ai.schemas import AgentEvent
                    yield AgentEvent(type="done", data={})
                MockSup.return_value.handle = mock_handle

                with patch("edu_cloud.ai.runtime.CapabilityProbe") as MockProbe:
                    MockProbe.return_value.determine_tier = AsyncMock(return_value=3)

                    with patch("edu_cloud.ai.runtime.LLMProxyAdapter"):
                        runtime = AgentRuntime()
                        ctx = AgentContext(
                            db=MagicMock(), user_id="u1", school_id="sch1",
                            role="teacher", data_scope=MockDataScope(),
                            session_id="s1",
                            user_slots=[MagicMock(api_url="http://test", slot_number=1)],
                            system_slots=[], enhanced_enabled=False,
                        )

                        async for _ in runtime.run("hello", ctx):
                            pass

                        MockRouter.return_value.route.assert_called_once()
```

- [ ] **Step 2: Run tests — should FAIL**

- [ ] **Step 3: Implement AgentRuntime**

```python
# src/edu_cloud/ai/runtime.py
"""AgentRuntime: transport-agnostic Agent execution."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.ai.capability_probe import CapabilityProbe, LoopStrategy
from edu_cloud.ai.grounded import OutputValidator
from edu_cloud.ai.llm_adapter import LLMProxyAdapter
from edu_cloud.ai.memory_extractor import MemoryExtractor
from edu_cloud.ai.memory_injector import MemoryInjector
from edu_cloud.ai.memory_store import MemoryStore
from edu_cloud.ai.model_router import ModelRouter
from edu_cloud.ai.registry import tools as tool_registry
from edu_cloud.ai.schemas import AgentEvent
from edu_cloud.ai.sensitivity_router import SensitivityRouter
from edu_cloud.ai.supervisor import Supervisor
from edu_cloud.ai.agent_team import teams as default_team_registry
from edu_cloud.ai.tool_access import ToolAccessResolver
from edu_cloud.ai.tool_context import ToolContext

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentContext:
    """All context for one Agent invocation."""
    db: AsyncSession
    user_id: str
    school_id: str
    role: str
    data_scope: Any
    session_id: str
    user_slots: list[Any] = field(default_factory=list)
    system_slots: list[Any] = field(default_factory=list)
    enhanced_enabled: bool = False
    # Optional overrides
    class_ids: list[str] | None = None
    subject_codes: list[str] | None = None
    capabilities: dict[tuple[str, str], bool] = field(default_factory=dict)
    enabled_modules: list[str] = field(default_factory=list)
    display_name: str = ""
    school_name: str = ""
    anonymizer: Any | None = None  # F004 fix: Anonymizer 注入（HTTP 入口必传）


class AgentRuntime:
    """Stateless Agent runtime. Each run() is independent."""

    def __init__(self):
        self._model_router = ModelRouter()
        self._memory_store = MemoryStore()
        self._memory_injector = MemoryInjector(store=self._memory_store)
        self._memory_extractor = MemoryExtractor(store=self._memory_store)
        self._validator = OutputValidator()
        self._probe = CapabilityProbe()
        self._tool_resolver = ToolAccessResolver()

    async def run(
        self,
        message: str,
        context: AgentContext,
        history: list | None = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        """Execute Agent pipeline. Yields AgentEvent stream."""

        # 1. Model routing (F002 fix: 沿用 llm-proxy，不直接用 slot.api_url)
        from edu_cloud.config import settings
        model_choice = self._model_router.route(
            message, context.user_slots, context.system_slots,
            enhanced_enabled=context.enhanced_enabled,
        )
        # ModelRouter 只决定 tier，实际连接始终走 llm-proxy
        slot_name = "ai-chat"  # 默认逻辑槽位
        if model_choice.tier == "advanced" and context.system_slots:
            slot_name = "ai-enhanced"
        adapter = LLMProxyAdapter(
            base_url=settings.LLM_API_URL or "http://localhost:8100",
            slot=slot_name,
        )

        # 2. Capability probe
        tier = await self._probe.determine_tier(adapter)
        strategy = LoopStrategy.for_tier(tier)

        # 3. Memory injection (Tier 1-2)
        memory_context = ""
        if tier <= 2:
            try:
                memory_context = await self._memory_injector.build_context(
                    db=context.db, school_id=context.school_id,
                    user_id=context.user_id, role=context.role,
                    class_ids=context.class_ids,
                    student_ids=(context.data_scope.visible_student_ids
                                 if context.data_scope else None),
                )
            except Exception:
                logger.exception("Memory injection failed (non-blocking)")

        # 4. Tool resolution
        available_tools = self._tool_resolver.resolve(
            tool_registry.all_specs(),
            role=context.role,
            enabled_modules=context.enabled_modules,
            capabilities=context.capabilities,
        )

        # 5. Build prompt
        from edu_cloud.ai.prompts import build_teacher_prompt
        tool_names = [t.name for t in available_tools]
        system_prompt = build_teacher_prompt(
            role=context.role,
            display_name=context.display_name,
            school_name=context.school_name,
            tool_names=tool_names,
            tier=tier,
        ) + memory_context

        # 6. Build ToolContext (F004 fix: 保留 anonymizer)
        tool_ctx = ToolContext(
            db=context.db,
            school_id=context.school_id,
            user_id=context.user_id,
            role=context.role,
            class_ids=context.class_ids,
            subject_codes=context.subject_codes,
            capabilities=context.capabilities,
            enabled_modules=context.enabled_modules,
            data_scope=context.data_scope,
            anonymizer=context.anonymizer,
        )

        # 7. Supervisor (F001 fix: 保留 team_registry + sensitivity_router)
        mem_extractor = self._memory_extractor if strategy.tier == 1 else None
        sensitivity_router = SensitivityRouter(primary=adapter, enhanced=None)
        supervisor = Supervisor(
            registry=tool_registry,
            adapter=adapter,
            strategy=strategy,
            team_registry=default_team_registry,
            sensitivity_router=sensitivity_router,
            memory_extractor=mem_extractor,
        )

        # 8. Execute and yield events
        async for event in supervisor.handle(
            message=message,
            ctx=tool_ctx,
            tool_specs=available_tools,
            system_prompt=system_prompt,
            history=history,
            session_id=context.session_id,
        ):
            yield event
```

- [ ] **Step 4: Run tests — should PASS**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_runtime.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/ai/runtime.py tests/test_ai/test_runtime.py
git commit -m "feat(runtime): add AgentRuntime + AgentContext — transport-agnostic entry"
```

---

### Task 5: Grounded Prompt 规则 + AgentLoop 接入 OutputValidator

**Files:**
- Modify: `src/edu_cloud/ai/prompts.py`
- Modify: `src/edu_cloud/ai/agent_loop.py`（小改：answer 前校验）
- Test: `tests/test_ai/test_grounded.py`（追加集成测试）

**测试契约:**
1. Grounded 规则出现在 system prompt 中
   - 入口: `build_teacher_prompt(...)` 返回值包含 "数据引用规则"
   - 反例: 忘记添加规则段
   - 边界: N/A
   - 回归: 现有 prompt 结构不变
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_grounded.py::TestGroundedPrompt -v`

**审查清单:**
- ✓ Grounded 规则追加到 prompt 末尾，不破坏现有结构
- ✓ AgentLoop 修改最小化（仅在 yield answer event 前插入校验）
- ✗ 不修改 Supervisor

**边界条件:**
- validator 返回 pass → 原样 yield
- validator 返回 warn → 原样 yield（warn 标注由上层决定）
- validator 返回 fail → 原样 yield（拦截由上层 AgentRuntime 决定）

NOTE (F003 fix): AgentLoop 层不修改 event.data（保持 SSE 事件 shape 兼容）。OutputValidator 的校验结果仅在 AgentRuntime 内部消费（日志记录 + 统计），不附加到任何事件上。拦截/重新生成逻辑在 AgentRuntime.run() 中，前端 SSE 消费方不感知。

- [ ] **Step 1: Write tests**

```python
# tests/test_ai/test_grounded.py（追加）

class TestGroundedPrompt:
    def test_prompt_contains_grounded_rules(self):
        from edu_cloud.ai.prompts import build_teacher_prompt
        prompt = build_teacher_prompt(
            role="subject_teacher",
            display_name="李老师",
            school_name="育才中学",
            tool_names=["get_class_stats"],
            tier=1,
        )
        assert "数据引用规则" in prompt
        assert "禁止凭推测" in prompt or "禁止" in prompt
```

- [ ] **Step 2: Run test — should FAIL**

- [ ] **Step 3: Add Grounded rules to prompts.py**

In `src/edu_cloud/ai/prompts.py`, add at the end of `build_teacher_prompt()` before the return:

```python
    # Grounded Generation rules
    parts.append("""## 数据引用规则
1. 涉及具体数值（分数、百分比、排名、人数）时，必须标注来源
2. 格式：数值（来源：XX考试/XX时间）
3. 禁止凭推测给出具体数值
4. 工具未返回的数据，说"暂无该数据"，不要编造""")
```

- [ ] **Step 4: Run test — should PASS**

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/ai/prompts.py tests/test_ai/test_grounded.py
git commit -m "feat(runtime): add Grounded Generation prompt rules"
```

---

### Task 6: Worker 入口 + 事件触发

**Files:**
- Modify: `src/edu_cloud/worker.py`
- Modify: `src/edu_cloud/core/events.py`
- Test: `tests/test_ai/test_runtime.py`（追加 worker 测试）

**测试契约:**
1. run_agent_scheduled 函数可调用
   - 入口: `run_agent_scheduled(ctx, school_id, task_type, params)`
   - 反例: 函数未注册到 worker
   - 边界: 未知 task_type / school 无启用模块
   - 回归: 现有 worker 函数不变
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_runtime.py::TestWorkerEntry -v`

**审查清单:**
- ✓ 函数注册到 WorkerSettings.functions
- ✓ 事件入队异步（不阻塞发布流程）
- ✓ 检查学校模块开关
- ✗ 不实现具体定时任务（只留接口）

**边界条件:**
- 未知 task_type → 记日志，不抛异常
- 学校模块未启用 → 跳过

- [ ] **Step 1: Write tests**

```python
# tests/test_ai/test_runtime.py（追加）

class TestWorkerEntry:
    def test_worker_function_registered(self):
        from edu_cloud.worker import WorkerSettings
        func_names = [f.__name__ if callable(f) else f.coroutine.__name__
                      for f in WorkerSettings.functions]
        assert "run_agent_scheduled" in func_names

    def test_scheduled_prompts_exist(self):
        from edu_cloud.ai.runtime import SCHEDULED_PROMPTS
        assert "exam_analysis" in SCHEDULED_PROMPTS
```

- [ ] **Step 2: Run tests — should FAIL**

- [ ] **Step 3: Add SCHEDULED_PROMPTS to runtime.py**

```python
# src/edu_cloud/ai/runtime.py（追加到文件末尾）

SCHEDULED_PROMPTS: dict[str, str] = {
    "daily_grade_alert": "检查今天是否有异常成绩数据，如有则生成预警摘要。",
    "weekly_class_report": "生成本周各班级的成绩变化摘要报告。",
    "exam_analysis": "对刚发布的考试进行全面分析：成绩分布、薄弱知识点、班级对比。",
}
```

- [ ] **Step 4: Add run_agent_scheduled to worker.py**

Read `src/edu_cloud/worker.py` first. Then add:

```python
from edu_cloud.ai.runtime import AgentRuntime, AgentContext, SCHEDULED_PROMPTS

async def run_agent_scheduled(ctx, school_id: str, task_type: str, params: dict):
    """Scheduled Agent task — uses school's own model slots."""
    prompt = SCHEDULED_PROMPTS.get(task_type)
    if not prompt:
        logger.warning("Unknown agent task_type: %s", task_type)
        return
    # Full implementation deferred — this is the interface hook
    logger.info("Agent scheduled task: school=%s type=%s", school_id, task_type)
```

Add to `WorkerSettings.functions` list:
```python
functions = [...existing..., run_agent_scheduled]
```

- [ ] **Step 5: Add event handler to events.py**

Read `src/edu_cloud/core/events.py`. Add after existing handlers:

```python
@event_bus.on("exam.published")
async def on_exam_published_agent(payload: dict):
    """Trigger Agent analysis when exam is published (if module enabled)."""
    logger.info("event_bus: exam.published → agent analysis queued for school %s",
                payload.get("school_id"))
    # Actual enqueue deferred until arq pool is wired
```

- [ ] **Step 6: Run tests — should PASS**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_runtime.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/worker.py src/edu_cloud/core/events.py src/edu_cloud/ai/runtime.py tests/test_ai/test_runtime.py
git commit -m "feat(runtime): add Worker entry + event trigger hooks"
```

---

### Task 7: CLI 入口（仅参数解析，F005 降级）

> F005 fix: CLI 本 Task 只实现参数解析和模块框架。实际运行需要 DB 连接 + slot 构造，
> 留 Phase C 补齐。`_run()` 中标注 `# TODO: Phase C — wire DB + slot lookup`。

**Files:**
- Create: `src/edu_cloud/cli/__init__.py`
- Create: `src/edu_cloud/cli/agent.py`
- Test: `tests/test_ai/test_agent_cli.py`

**测试契约:**
1. CLI 参数解析
   - 入口: `parse_args(["--school", "YCSY2026", "--role", "principal", "分析成绩"])`
   - 反例: 缺少必选参数不报错
   - 边界: 无消息参数 / 未知角色
   - 回归: N/A
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_agent_cli.py -v`

**审查清单:**
- ✓ 使用 argparse
- ✓ 非交互式（单次执行）
- ✗ 不做 REPL
- ✗ 不宣称可执行（_run 为 placeholder）

**边界条件:**
- 缺 --school → 报错退出
- 缺消息 → 报错退出
- 正常参数 → parse 成功（实际运行需 DB）

- [ ] **Step 1: Write tests**

```python
# tests/test_ai/test_agent_cli.py
import pytest
from edu_cloud.cli.agent import parse_args


class TestCLIArgs:
    def test_parse_valid(self):
        args = parse_args(["--school", "YCSY2026", "--role", "principal", "分析成绩"])
        assert args.school == "YCSY2026"
        assert args.role == "principal"
        assert args.message == "分析成绩"

    def test_missing_school(self):
        with pytest.raises(SystemExit):
            parse_args(["--role", "principal", "分析"])

    def test_missing_message(self):
        with pytest.raises(SystemExit):
            parse_args(["--school", "YCSY2026", "--role", "principal"])

    def test_default_role(self):
        args = parse_args(["--school", "YCSY2026", "分析成绩"])
        assert args.role == "principal"
```

- [ ] **Step 2: Run tests — should FAIL**

- [ ] **Step 3: Implement CLI**

```python
# src/edu_cloud/cli/__init__.py
# empty package

# src/edu_cloud/cli/agent.py
"""CLI entry point for Agent — single-shot execution."""

import argparse
import asyncio
import json
import sys


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="edu-agent",
        description="edu-cloud Agent CLI — single-shot execution",
    )
    parser.add_argument("--school", required=True, help="School code (e.g. YCSY2026)")
    parser.add_argument("--role", default="principal", help="Role (default: principal)")
    parser.add_argument("message", help="Message to send to Agent")
    return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> None:
    """Execute Agent and print JSON lines to stdout."""
    # Deferred import to avoid loading full app on parse_args tests
    from edu_cloud.ai.runtime import AgentRuntime, AgentContext
    from edu_cloud.database import async_session

    async with async_session() as db:
        # Build minimal context (full implementation when DB wired)
        ctx = AgentContext(
            db=db,
            user_id="cli",
            school_id=args.school,
            role=args.role,
            data_scope=None,
            session_id="cli-session",
            user_slots=[],
            system_slots=[],
            enhanced_enabled=False,
        )

        runtime = AgentRuntime()
        async for event in runtime.run(args.message, ctx):
            print(json.dumps(event.to_dict(), ensure_ascii=False))


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests — should PASS**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_agent_cli.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/cli/ tests/test_ai/test_agent_cli.py
git commit -m "feat(runtime): add CLI entry point — edu-agent single-shot"
```

---

### Task 8: api/ai.py 瘦身（迁移到 AgentRuntime）

**Files:**
- Modify: `src/edu_cloud/api/ai.py`
- Test: 现有 `tests/test_ai/test_ai_api.py` + `tests/test_ai/test_ai_api_v2.py` 回归

这个 Task 是渐进式迁移：保留现有 HTTP 端点行为不变，内部改为调用 AgentRuntime。由于 api/ai.py 较复杂（会话管理、SSE、profile 等），此 Task 分两步：

Step 1: 在 chat 端点中创建 AgentContext，调 AgentRuntime.run()，替代直接构造 Supervisor
Step 2: 跑全量测试确认零回归

NOTE: 需要先读当前 api/ai.py 的完整代码，理解 session 管理、profile 逻辑后再改。改动原则是最小化——只替换 Supervisor 构造和 handle 调用，其他逻辑（session、SSE、profile）保留。

**测试契约（F006 fix）:**
1. SSE 事件 shape 兼容
   - 入口: `POST /api/v1/ai/chat` body=`{"message": "test"}`
   - 反例: 错误实现改变 event.data 结构导致前端解析失败
   - 边界: answer/tool_call/tool_result/done 四种事件类型 shape 不变
   - 回归: 防止 F003 SSE shape 回退
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_ai_api_v2.py -v`
2. Session owner 隔离
   - 入口: `DELETE /api/v1/ai/sessions/{session_id}` 用另一用户 token
   - 反例: 错误实现丢失 owner_id 导致任意用户可删他人会话
   - 边界: session 不存在 / 本人会话 / 他人会话
   - 回归: 现有 403 行为不变
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_ai_api.py -v -k session`
3. AgentProfile record_run 持久化
   - 入口: `POST /api/v1/ai/chat` → event_stream finally 块
   - 反例: 错误实现遗漏 record_run 导致 agent_runs 表无记录
   - 边界: profile 创建失败时不阻塞响应
   - 回归: N/A
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_ai_api.py -v -k profile`
4. Anonymizer 注入不丢失（F004 验证）
   - 入口: `POST /api/v1/ai/chat` → ToolContext.anonymizer is not None
   - 反例: 错误实现构造 AgentContext 时遗漏 anonymizer
   - 边界: 新 session（新建 Anonymizer）/ 已有 session（复用 Anonymizer）
   - 回归: 防止 F004 隐私保护失效
   - 命令: `cd ~/edu-cloud && python -m pytest tests/test_ai/ -v -k anonymi`

**审查清单:**
- ✓ 所有现有 AI 测试通过
- ✓ SSE 格式不变（F003）
- ✓ Session 管理不变
- ✓ Profile 逻辑不变
- ✓ Anonymizer 注入不丢失（F004）
- ✓ team_registry + sensitivity_router 传入（F001）
- ✗ 不删除 api/ai.py 中的其他端点（health/sessions）

**边界条件:**
- 空消息 → 返回 error 响应（现有行为不变）
- Supervisor 构造失败 → fallback 到 tier3（现有 try/except 保留）
- DataScope 构建失败 → 继续运行（现有 graceful 降级保留）

- [ ] **Step 1: Read current api/ai.py completely**

- [ ] **Step 2: Refactor chat endpoint to use AgentRuntime**

Replace Supervisor construction + handle with:

```python
    # Create AgentContext (F001+F004 fix: 保留 anonymizer)
    agent_ctx = AgentContext(
        db=db,
        user_id=str(user.id),
        school_id=school_id,
        role=role,
        data_scope=data_scope,
        session_id=session_id,
        user_slots=user_slots,  # from DB
        system_slots=system_slots,  # from DB
        enhanced_enabled=enhanced_enabled,  # from school settings
        class_ids=scope.get("classes"),
        subject_codes=scope.get("subjects"),
        capabilities=capabilities,
        enabled_modules=enabled_modules,
        display_name=user.display_name or "",
        school_name=school_name or "",
        anonymizer=session_state.anonymizer,  # F004: 隐私保护不丢失
    )
    
    runtime = AgentRuntime()
    
    async def event_stream():
        async for event in runtime.run(
            message=req.message,
            context=agent_ctx,
            history=session_state.history if session_state else None,
        ):
            yield f"data: {json.dumps(event.to_dict(), ensure_ascii=False)}\n\n"
```

- [ ] **Step 3: Run full AI test suite**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/ --tb=short -q`
Expected: All tests PASS

- [ ] **Step 4: Run full test suite**

Run: `cd ~/edu-cloud && python -m pytest --tb=short -q`
Expected: All tests PASS (same as before, minus 2 pre-existing failures)

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/api/ai.py
git commit -m "refactor(runtime): api/ai.py chat endpoint uses AgentRuntime"
```

---

### Task 9: 全量回归 + 验证

**Files:** 无新文件

- [ ] **Step 1: Run full test suite**

Run: `cd ~/edu-cloud && python -m pytest --tb=short -q`
Expected: All tests PASS

- [ ] **Step 2: Count new tests**

Run: `cd ~/edu-cloud && python -m pytest tests/test_ai/test_runtime.py tests/test_ai/test_model_router.py tests/test_ai/test_grounded.py tests/test_ai/test_agent_cli.py -v 2>&1 | tail -5`

- [ ] **Step 3: Verify git diff**

Run: `cd ~/edu-cloud && git diff --stat HEAD~8`

- [ ] **Step 4: Tag**

```bash
git tag -a v0.11.0-agent-runtime -m "Agent Runtime: multi-entry + dual-model + grounded generation"
```

---

## Contract Pack（F007 fix: 对齐 contract-pack-schema.md）

```yaml
contract_pack:
  invariants:
    - id: INV-001
      statement: "AgentRuntime.run() 每次调用独立：不共享会话历史、不缓存模型实例、不跨调用保留记忆状态"
      verification: pending_test
      test_ref: "tests/test_ai/test_runtime.py::TestAgentRuntime::test_run_yields_events"
    - id: INV-002
      statement: "ModelRouter.route() 不调用 LLM：纯关键词匹配 + 标志判断，零 token 消耗"
      verification: pending_test
      test_ref: "tests/test_ai/test_model_router.py::TestModelRouter"
    - id: INV-003
      statement: "enhanced_enabled=False 时 ModelRouter 始终返回 tier=standard，不尝试 system_slots"
      verification: pending_test
      test_ref: "tests/test_ai/test_model_router.py::TestModelRouter::test_enhanced_disabled_uses_user"
    - id: INV-004
      statement: "OutputValidator.validate() 不调用 LLM：纯正则提取 + 数值集合比对"
      verification: pending_test
      test_ref: "tests/test_ai/test_grounded.py::TestOutputValidator"
    - id: INV-005
      statement: "ToolResult(source=None) 时 to_dict() 不包含 source 键，现有 42 个工具无需修改"
      verification: pending_test
      test_ref: "tests/test_ai/test_grounded.py::TestToolResultSource::test_backward_compat_existing_usage"

  counter_examples:
    - id: CE-001
      scenario: "OutputValidator 总返回 pass（空实现）：Agent 声称'平均分 85'但工具返回 avg=72.3，不会被拦截"
      tests_that_still_pass: "test_no_tools_pass, test_no_numbers_pass（这些本身就应该 pass）"
      mitigation: "test_contradicting_number_fail 断言 status=='fail'，空实现会失败"
    - id: CE-002
      scenario: "ModelRouter 忽略 enhanced_enabled 标志：所有请求都走 system_slots，基础版用户消耗系统资源"
      tests_that_still_pass: "test_complex_analysis_uses_system（增强用户的复杂请求本就走 advanced）"
      mitigation: "test_enhanced_disabled_uses_user 断言 tier=='standard'，忽略标志会失败"

  risk_modules:
    - module: "src/edu_cloud/ai/runtime.py"
      reason: "统一调度器，api/ai.py 迁移后 HTTP/Worker/CLI 三入口均依赖此模块"
    - module: "src/edu_cloud/ai/grounded.py"
      reason: "数值提取正则覆盖中文量词（分/人/名/次等），遗漏模式导致 warn/fail 误判"
    - module: "src/edu_cloud/api/ai.py"
      reason: "瘦身重构涉及 SSE/session/profile/anonymizer 四条契约链"

  test_debt:
    - item: "OutputValidator 对中文模糊表述（'约七十分'）不做提取"
      reason: "正则只覆盖精确数值+量词模式，模糊表述是 LLM 风格问题，不属于幻觉检测范围"
      deadline: "2099-12-31"
    - item: "CLI 端到端测试需要 DB 连接，当前只测参数解析"
      reason: "CLI 定位为调试工具（F005 降级），AgentRuntime 已有独立单测覆盖"
      deadline: "2099-12-31"
```

## 审查清单（全局）

- ✓ AgentRuntime 无状态，每次 run() 独立
- ✓ ModelRouter 零 token 消耗
- ✓ 主力模型能独立运行全部功能
- ✓ OutputValidator 零 token，纯数值比对
- ✓ ToolResult.source 向后兼容
- ✓ Worker/CLI/HTTP 三入口共用 AgentRuntime
- ✓ Grounded 规则注入 system prompt
- ✓ 现有 Supervisor/AgentLoop/Tools 不修改核心逻辑
- ✓ [F001] Supervisor 保留 team_registry + sensitivity_router
- ✓ [F002] LLM 连接沿用 llm-proxy，不直接用 slot.api_url
- ✓ [F003] SSE event shape 不变，校验结果仅 runtime 内部消费
- ✓ [F004] Anonymizer 注入链完整（AgentContext → ToolContext）
- ✓ [F005] CLI 降级为参数解析，不宣称可执行
- ✓ [F006] Task 8 补完整测试契约（SSE/session/profile/anonymizer）
- ✓ [F007] Contract Pack 对齐 schema 字段名和格式
- ✗ 42 个工具的 source 标签逐步迁移（不在本次范围）
- ✗ 定时任务具体实现留接口（Phase C）
