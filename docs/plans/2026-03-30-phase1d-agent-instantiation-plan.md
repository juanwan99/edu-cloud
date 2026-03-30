# Phase 1d: Agent 核心基础设施 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 AI Agent 从 flat 工具列表升级为身份驱动 + 三重权限过滤 + 意图裁剪 + 模型分层路由。

**Architecture:** AgentProfile 持久化 Agent 身份，ToolAccessResolver 三重过滤（RBAC ∩ Module ∩ Capability）替代 ROLE_TOOL_CATEGORIES，IntentResolver 规则+LLM 裁剪工具集，ModelRouter 按场景选 LLMSlot tier。Pipeline 插入 ai.py 的 ai_chat() 端点，Agent.run() 核心不变。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + Alembic + pytest (async)

**Design doc:** `docs/plans/2026-03-30-phase1d-agent-instantiation-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `src/edu_cloud/models/agent_profile.py` | AgentProfile + AgentRun ORM |
| Create | `src/edu_cloud/ai/tool_access.py` | ToolAccessResolver（三重过滤） |
| Create | `src/edu_cloud/ai/intent_resolver.py` | IntentResolver（规则+LLM 后备） |
| Create | `src/edu_cloud/ai/model_router.py` | ModelRouter（tier 选择） |
| Create | `src/edu_cloud/ai/llm_factory.py` | create_llm_for_tier() 工厂 |
| Create | `src/edu_cloud/services/agent_profile_service.py` | Profile CRUD + get_or_create |
| Modify | `src/edu_cloud/ai/registry.py` | ToolSpec dataclass + register 扩展 |
| Modify | `src/edu_cloud/ai/agent.py` | 删除 ROLE_TOOL_CATEGORIES + run() 接收 tools 参数 |
| Modify | `src/edu_cloud/api/ai.py` | Pipeline 集成 |
| Modify | `src/edu_cloud/ai/llm.py` | chat() 支持简单文本返回 |
| Modify | `src/edu_cloud/core/models/llm_slot.py` | 添加 tier 字段 |
| Modify | `src/edu_cloud/ai/tools/*.py` | 31 工具添加元数据 |
| Modify | `alembic/env.py` | 导入新模型 |
| Modify | `tests/conftest.py` | 导入新模型 |
| Modify | `tests/test_alembic_migration.py` | 更新表集合 |
| Modify | `CLAUDE.md` | 同步架构变更 |
| Create | `tests/test_services/test_agent_profile_service.py` | Profile 测试 |
| Create | `tests/test_ai/test_tool_access.py` | ToolAccessResolver 测试 |
| Create | `tests/test_ai/test_intent_resolver.py` | IntentResolver 测试 |
| Create | `tests/test_ai/test_model_router.py` | ModelRouter 测试 |
| Create | `tests/test_ai/test_agent_pipeline.py` | 端到端集成测试 |

---

### Task 1: ToolSpec Dataclass + Registry 升级

**Files:**
- Modify: `src/edu_cloud/ai/registry.py`
- Create: `tests/test_ai/test_registry_upgrade.py`

- [ ] **Step 1: Write failing tests for ToolSpec metadata**

```python
# tests/test_ai/test_registry_upgrade.py
import pytest
from edu_cloud.ai.registry import ToolRegistry, ToolSpec


def test_toolspec_has_metadata_fields():
    spec = ToolSpec(
        name="test_tool",
        description="A test",
        parameters={},
        func=lambda: None,
        module_code="exam",
        domain="analytics",
        risk_level="low",
        allowed_roles=["platform_admin"],
        requires_capabilities=[("exam", "view")],
    )
    assert spec.module_code == "exam"
    assert spec.domain == "analytics"
    assert spec.risk_level == "low"
    assert spec.allowed_roles == ["platform_admin"]
    assert spec.requires_capabilities == [("exam", "view")]


def test_toolspec_defaults():
    spec = ToolSpec(name="t", description="d", parameters={}, func=lambda: None)
    assert spec.module_code is None
    assert spec.domain == "general"
    assert spec.risk_level == "low"
    assert spec.allowed_roles is None
    assert spec.requires_capabilities == []


def test_register_with_metadata():
    reg = ToolRegistry()

    @reg.register(
        name="my_tool",
        description="Test",
        parameters={"type": "object", "properties": {}},
        module_code="exam",
        domain="analytics",
        risk_level="med",
    )
    async def my_tool():
        return {}

    specs = reg.get_all_specs()
    assert len(specs) == 1
    assert specs[0].module_code == "exam"
    assert specs[0].domain == "analytics"


def test_register_backward_compat():
    """现有 category 参数仍可用"""
    reg = ToolRegistry()

    @reg.register(
        name="old_tool",
        description="Legacy",
        parameters={},
        category="L1_exam",
    )
    async def old_tool():
        return {}

    specs = reg.get_all_specs()
    assert specs[0].category == "L1_exam"
    assert specs[0].domain == "general"  # 未指定 domain 时默认


def test_get_schemas_still_works():
    """确保现有 get_schemas(categories=...) 不崩溃"""
    reg = ToolRegistry()

    @reg.register(name="t1", description="d", parameters={}, category="L1_exam")
    async def t1():
        return {}

    schemas = reg.get_schemas(categories=["L1_exam"])
    assert len(schemas) == 1
    assert schemas[0]["function"]["name"] == "t1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_registry_upgrade.py -v`
Expected: ImportError for ToolSpec, AttributeError for get_all_specs

- [ ] **Step 3: Implement ToolSpec dataclass and upgrade ToolRegistry**

```python
# src/edu_cloud/ai/registry.py — 完整重写
import inspect
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict
    func: Callable
    category: str = "general"
    module_code: str | None = None
    domain: str = "general"
    requires_capabilities: list[tuple[str, str]] = field(default_factory=list)
    risk_level: str = "low"
    allowed_roles: list[str] | None = None


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
    ):
        def decorator(func):
            self._tools[name] = ToolSpec(
                name=name,
                description=description,
                parameters=parameters or {"type": "object", "properties": {}},
                func=func,
                category=category,
                module_code=module_code,
                domain=domain,
                requires_capabilities=requires_capabilities or [],
                risk_level=risk_level,
                allowed_roles=allowed_roles,
            )
            return func
        return decorator

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get_all_specs(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def get_schemas(self, categories: list[str] | None = None) -> list[dict]:
        """向后兼容：按 category 过滤返回 OpenAI function schema"""
        result = []
        for spec in self._tools.values():
            if categories is not None and spec.category not in categories:
                continue
            result.append({
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters,
                },
            })
        return result

    async def execute(self, name: str, arguments: dict, **injected) -> dict:
        if name not in self._tools:
            return {"error": f"Unknown tool: {name}"}
        spec = self._tools[name]
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


tools = ToolRegistry()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_registry_upgrade.py -v`
Expected: 5 passed

- [ ] **Step 5: Run existing AI tests to verify backward compat**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/ -v`
Expected: 全部 pass（现有测试不受影响）

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/ai/registry.py tests/test_ai/test_registry_upgrade.py
git commit -m "feat: upgrade ToolRegistry with ToolSpec dataclass and metadata fields"
```

**审查清单:**
- ✓ ToolSpec 包含 7 个元数据字段（module_code, domain, requires_capabilities, risk_level, allowed_roles, category, func）
- ✓ register() 新增可选参数，旧调用方式不受影响
- ✓ get_schemas(categories=...) 向后兼容
- ✓ get_all_specs() 返回 ToolSpec 对象列表
- ✗ register() 缺少 name 参数应报错而非静默
- ✗ execute() 对不存在工具应返回 error dict 而非抛异常

**边界条件:**
- 空注册表调用 get_all_specs() → 返回 []
- category=None 调用 get_schemas() → 返回全部
- category=[] 调用 get_schemas() → 返回空（无权限）

---

### Task 2: AgentProfile + AgentRun 模型

**Files:**
- Create: `src/edu_cloud/models/agent_profile.py`
- Create: `tests/test_services/test_agent_profile_service.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_services/test_agent_profile_service.py
import pytest
from edu_cloud.models.agent_profile import AgentProfile, AgentRun


@pytest.mark.asyncio
async def test_create_agent_profile(db):
    profile = AgentProfile(
        owner_user_id="user-uuid-1",
        school_id="school-uuid-1",
        profile_type="employee",
        display_name="张老师的助手",
    )
    db.add(profile)
    await db.flush()
    assert profile.id is not None
    assert profile.profile_type == "employee"
    assert profile.preferences is None
    assert profile.memory_summary is None


@pytest.mark.asyncio
async def test_agent_profile_unique_constraint(db):
    """同一用户同一学校只能有一个 profile"""
    from sqlalchemy.exc import IntegrityError
    p1 = AgentProfile(
        owner_user_id="user-1", school_id="school-1",
        profile_type="employee", display_name="A",
    )
    p2 = AgentProfile(
        owner_user_id="user-1", school_id="school-1",
        profile_type="employee", display_name="B",
    )
    db.add(p1)
    await db.flush()
    db.add(p2)
    with pytest.raises(IntegrityError):
        await db.flush()


@pytest.mark.asyncio
async def test_create_agent_run(db):
    profile = AgentProfile(
        owner_user_id="user-1", school_id="school-1",
        profile_type="employee", display_name="Test",
    )
    db.add(profile)
    await db.flush()

    run = AgentRun(
        profile_id=profile.id,
        session_id="sess-123",
        tools_resolved=["tool_a", "tool_b", "tool_c"],
        tools_selected=["tool_a"],
        model_used="gpt-5-mini",
        model_tier="mini",
        intent_domains=["exam"],
        token_input=100,
        token_output=50,
    )
    db.add(run)
    await db.flush()
    assert run.id is not None
    assert run.tools_resolved == ["tool_a", "tool_b", "tool_c"]


@pytest.mark.asyncio
async def test_agent_profile_system_type(db):
    profile = AgentProfile(
        owner_user_id="system", school_id="school-1",
        profile_type="system", display_name="巡检 Agent",
    )
    db.add(profile)
    await db.flush()
    assert profile.profile_type == "system"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_agent_profile_service.py -v`
Expected: ImportError

- [ ] **Step 3: Implement models**

```python
# src/edu_cloud/models/agent_profile.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class AgentProfile(Base, IdMixin, TimestampMixin):
    __tablename__ = "agent_profiles"

    owner_user_id: Mapped[str] = mapped_column(String(36), index=True)
    school_id: Mapped[str] = mapped_column(String(36), index=True)
    profile_type: Mapped[str] = mapped_column(String(20), default="employee")
    display_name: Mapped[str] = mapped_column(String(100))
    preferences: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    memory_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("owner_user_id", "school_id", name="uq_profile_user_school"),
    )


class AgentRun(Base, IdMixin):
    __tablename__ = "agent_runs"

    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_profiles.id"), index=True
    )
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    tools_resolved: Mapped[list] = mapped_column(JSON, default=list)
    tools_selected: Mapped[list] = mapped_column(JSON, default=list)
    model_used: Mapped[str] = mapped_column(String(50))
    model_tier: Mapped[str] = mapped_column(String(20))
    intent_domains: Mapped[list] = mapped_column(JSON, default=list)
    token_input: Mapped[int] = mapped_column(default=0)
    token_output: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

- [ ] **Step 4: Add import to conftest.py**

在 `tests/conftest.py` 的模型 import 区域添加：
```python
import edu_cloud.models.agent_profile  # noqa: F401
```

- [ ] **Step 5: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_agent_profile_service.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/models/agent_profile.py tests/test_services/test_agent_profile_service.py tests/conftest.py
git commit -m "feat: add AgentProfile and AgentRun models"
```

**审查清单:**
- ✓ AgentProfile 有 UniqueConstraint(owner_user_id, school_id)
- ✓ AgentRun.session_id 用 String(36) 而非 FK（兼容现有 ai_sessions）
- ✓ 字段类型与现有模型一致（String(36) for UUIDs）
- ✗ owner_user_id 不存在的用户不应创建成功（但 SQLite 测试无 FK 约束）

**测试契约:**
1. 创建 Profile 唯一约束
   - 入口: `db.add(AgentProfile(same_user, same_school))`
   - 反例: 错误实现允许同用户同校多 profile → 本测试捕获 IntegrityError
   - 边界: 同用户不同校（应允许）/ 同校不同用户（应允许）
   - 回归: N/A
   - 命令: `pytest tests/test_services/test_agent_profile_service.py::test_agent_profile_unique_constraint -v`

---

### Task 3: AgentProfileService + get_or_create

**Files:**
- Create: `src/edu_cloud/services/agent_profile_service.py`
- Modify: `tests/test_services/test_agent_profile_service.py`

- [ ] **Step 1: Write failing tests**

追加到 `tests/test_services/test_agent_profile_service.py`：

```python
from edu_cloud.services.agent_profile_service import AgentProfileService


@pytest.mark.asyncio
async def test_get_or_create_creates_new(db):
    profile = await AgentProfileService.get_or_create(
        db, user_id="user-new", school_id="school-1", display_name="新用户"
    )
    assert profile.id is not None
    assert profile.owner_user_id == "user-new"
    assert profile.display_name == "新用户"


@pytest.mark.asyncio
async def test_get_or_create_returns_existing(db):
    p1 = await AgentProfileService.get_or_create(
        db, user_id="user-exist", school_id="school-1", display_name="First"
    )
    p2 = await AgentProfileService.get_or_create(
        db, user_id="user-exist", school_id="school-1", display_name="Second"
    )
    assert p1.id == p2.id
    assert p2.display_name == "First"  # 不覆盖已有


@pytest.mark.asyncio
async def test_create_agent_run_record(db):
    profile = await AgentProfileService.get_or_create(
        db, user_id="user-run", school_id="school-1", display_name="Run"
    )
    run = await AgentProfileService.record_run(
        db,
        profile_id=profile.id,
        session_id="sess-456",
        tools_resolved=["a", "b"],
        tools_selected=["a"],
        model_used="claude-sonnet-4",
        model_tier="standard",
        intent_domains=["exam", "student"],
        token_input=200,
        token_output=100,
    )
    assert run.id is not None
    assert run.model_tier == "standard"
```

- [ ] **Step 2: Implement service**

```python
# src/edu_cloud/services/agent_profile_service.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.agent_profile import AgentProfile, AgentRun


class AgentProfileService:
    @staticmethod
    async def get_or_create(
        db: AsyncSession, *, user_id: str, school_id: str, display_name: str
    ) -> AgentProfile:
        stmt = select(AgentProfile).where(
            AgentProfile.owner_user_id == user_id,
            AgentProfile.school_id == school_id,
        )
        result = await db.execute(stmt)
        profile = result.scalar_one_or_none()
        if profile:
            return profile
        profile = AgentProfile(
            owner_user_id=user_id,
            school_id=school_id,
            profile_type="employee",
            display_name=display_name,
        )
        db.add(profile)
        await db.flush()
        return profile

    @staticmethod
    async def record_run(
        db: AsyncSession,
        *,
        profile_id: str,
        session_id: str,
        tools_resolved: list[str],
        tools_selected: list[str],
        model_used: str,
        model_tier: str,
        intent_domains: list[str],
        token_input: int = 0,
        token_output: int = 0,
    ) -> AgentRun:
        run = AgentRun(
            profile_id=profile_id,
            session_id=session_id,
            tools_resolved=tools_resolved,
            tools_selected=tools_selected,
            model_used=model_used,
            model_tier=model_tier,
            intent_domains=intent_domains,
            token_input=token_input,
            token_output=token_output,
        )
        db.add(run)
        await db.flush()
        return run
```

- [ ] **Step 3: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_agent_profile_service.py -v`
Expected: 7 passed (4 旧 + 3 新)

- [ ] **Step 4: Commit**

```bash
git add src/edu_cloud/services/agent_profile_service.py tests/test_services/test_agent_profile_service.py
git commit -m "feat: add AgentProfileService with get_or_create and record_run"
```

**审查清单:**
- ✓ get_or_create 幂等（重复调用返回同一 profile）
- ✓ record_run 记录完整工具链路（resolved → selected）
- ✗ 并发 get_or_create 可能创建重复（DB 约束保护，应捕获 IntegrityError 重试）

---

### Task 4: ToolAccessResolver（三重过滤）

**Files:**
- Create: `src/edu_cloud/ai/tool_access.py`
- Create: `tests/test_ai/test_tool_access.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_tool_access.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from edu_cloud.ai.tool_access import ToolAccessResolver
from edu_cloud.ai.registry import ToolSpec


def _make_spec(name, category="general", module_code=None, domain="general",
               allowed_roles=None, requires_capabilities=None):
    return ToolSpec(
        name=name, description=f"Tool {name}", parameters={},
        func=AsyncMock(), category=category, module_code=module_code,
        domain=domain, allowed_roles=allowed_roles,
        requires_capabilities=requires_capabilities or [],
    )


@pytest.mark.asyncio
async def test_rbac_filter_blocks_unauthorized_role():
    specs = [
        _make_spec("admin_only", allowed_roles=["platform_admin"]),
        _make_spec("open_tool", allowed_roles=None),
    ]
    resolver = ToolAccessResolver()
    result = await resolver.resolve(
        all_specs=specs, role="subject_teacher",
        enabled_modules=set(), capabilities={},
    )
    assert len(result) == 1
    assert result[0].name == "open_tool"


@pytest.mark.asyncio
async def test_module_filter_blocks_disabled_module():
    specs = [
        _make_spec("exam_tool", module_code="exam"),
        _make_spec("no_module_tool"),
    ]
    resolver = ToolAccessResolver()
    result = await resolver.resolve(
        all_specs=specs, role="platform_admin",
        enabled_modules={"grading"},  # exam 未启用
        capabilities={},
    )
    assert len(result) == 1
    assert result[0].name == "no_module_tool"


@pytest.mark.asyncio
async def test_capability_filter_blocks_denied():
    specs = [
        _make_spec("cap_tool", requires_capabilities=[("exam", "view")]),
        _make_spec("no_cap_tool"),
    ]
    resolver = ToolAccessResolver()
    result = await resolver.resolve(
        all_specs=specs, role="platform_admin",
        enabled_modules=set(),
        capabilities={("exam", "view"): False},  # 显式拒绝
    )
    assert len(result) == 1
    assert result[0].name == "no_cap_tool"


@pytest.mark.asyncio
async def test_capability_default_allow():
    """未配置的 capability 默认允许"""
    specs = [_make_spec("cap_tool", requires_capabilities=[("exam", "view")])]
    resolver = ToolAccessResolver()
    result = await resolver.resolve(
        all_specs=specs, role="platform_admin",
        enabled_modules=set(), capabilities={},  # 未配置
    )
    assert len(result) == 1


@pytest.mark.asyncio
async def test_triple_filter_combined():
    specs = [
        _make_spec("full", allowed_roles=["academic_director"],
                   module_code="exam", requires_capabilities=[("exam", "manage")]),
        _make_spec("open"),
    ]
    resolver = ToolAccessResolver()
    # 角色匹配 + 模块启用 + capability 允许
    result = await resolver.resolve(
        all_specs=specs, role="academic_director",
        enabled_modules={"exam"},
        capabilities={("exam", "manage"): True},
    )
    assert len(result) == 2


@pytest.mark.asyncio
async def test_empty_specs():
    resolver = ToolAccessResolver()
    result = await resolver.resolve(
        all_specs=[], role="platform_admin",
        enabled_modules=set(), capabilities={},
    )
    assert result == []


@pytest.mark.asyncio
async def test_platform_admin_sees_all_role_restricted():
    """platform_admin 在 allowed_roles=None 时全看到"""
    specs = [_make_spec("restricted", allowed_roles=["platform_admin"])]
    resolver = ToolAccessResolver()
    result = await resolver.resolve(
        all_specs=specs, role="platform_admin",
        enabled_modules=set(), capabilities={},
    )
    assert len(result) == 1
```

- [ ] **Step 2: Implement ToolAccessResolver**

```python
# src/edu_cloud/ai/tool_access.py
from edu_cloud.ai.registry import ToolSpec


class ToolAccessResolver:
    """三重过滤：RBAC → Module → Capability"""

    async def resolve(
        self,
        all_specs: list[ToolSpec],
        role: str,
        enabled_modules: set[str],
        capabilities: dict[tuple[str, str], bool],
    ) -> list[ToolSpec]:
        result = []
        for spec in all_specs:
            # 层 1: RBAC
            if spec.allowed_roles is not None and role not in spec.allowed_roles:
                continue
            # 层 2: Module
            if spec.module_code and spec.module_code not in enabled_modules:
                continue
            # 层 3: Capability
            if not self._check_capabilities(spec.requires_capabilities, capabilities):
                continue
            result.append(spec)
        return result

    @staticmethod
    def _check_capabilities(
        required: list[tuple[str, str]],
        caps: dict[tuple[str, str], bool],
    ) -> bool:
        for domain, action in required:
            key = (domain, action)
            if key in caps and not caps[key]:
                return False
        return True
```

- [ ] **Step 3: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_tool_access.py -v`
Expected: 8 passed

- [ ] **Step 4: Commit**

```bash
git add src/edu_cloud/ai/tool_access.py tests/test_ai/test_tool_access.py
git commit -m "feat: add ToolAccessResolver with RBAC + Module + Capability triple filter"
```

**审查清单:**
- ✓ 三层过滤独立可测
- ✓ 宽松策略：未配置 capability 默认允许
- ✓ allowed_roles=None 表示不限角色
- ✗ 空 enabled_modules + module_code 存在时应拦截

**边界条件:**
- all_specs=[] → 返回 []
- 所有工具都被过滤 → 返回 []（调用方负责兜底）
- allowed_roles=[] → 所有角色被拒（空列表≠None）

**测试契约:**
1. 三重过滤组合
   - 入口: `resolver.resolve(specs, role, modules, caps)`
   - 反例: 只做单层过滤会透过不该暴露的工具——三层测试捕获此错误
   - 边界: 全拒/全允/单层拒
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_tool_access.py::test_triple_filter_combined -v`

---

### Task 5: IntentResolver（规则 + LLM 后备）

**Files:**
- Create: `src/edu_cloud/ai/intent_resolver.py`
- Create: `tests/test_ai/test_intent_resolver.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ai/test_intent_resolver.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from edu_cloud.ai.intent_resolver import IntentResolver, DOMAIN_RULES
from edu_cloud.ai.registry import ToolSpec


def _make_spec(name, domain="general"):
    return ToolSpec(
        name=name, description=f"Tool {name}", parameters={},
        func=AsyncMock(), domain=domain,
    )


def test_rule_match_chinese_exam():
    resolver = IntentResolver(llm_client=None)
    domains = resolver.resolve_by_rules("帮我查一下这次考试的成绩")
    assert "analytics" in domains  # "成绩"


def test_rule_match_chinese_student():
    resolver = IntentResolver(llm_client=None)
    domains = resolver.resolve_by_rules("三年一班的学生名单")
    assert "student" in domains


def test_rule_match_multi_domain():
    resolver = IntentResolver(llm_client=None)
    domains = resolver.resolve_by_rules("查一下这次考试每个学生的成绩排名")
    assert "analytics" in domains or "student" in domains
    assert len(domains) <= 3


def test_rule_no_match():
    resolver = IntentResolver(llm_client=None)
    domains = resolver.resolve_by_rules("你好，今天天气怎么样？")
    assert domains is None


@pytest.mark.asyncio
async def test_resolve_with_rules():
    all_tools = [
        _make_spec("get_scores", domain="analytics"),
        _make_spec("get_students", domain="student"),
        _make_spec("get_calendar", domain="calendar"),
    ]
    resolver = IntentResolver(llm_client=None)
    result = await resolver.resolve("帮我看看成绩", all_tools)
    assert any(t.name == "get_scores" for t in result)
    assert not any(t.name == "get_calendar" for t in result)
    assert resolver.last_domains == ["analytics"]


@pytest.mark.asyncio
async def test_resolve_fallback_to_all():
    """无匹配时返回全部工具"""
    all_tools = [_make_spec("t1"), _make_spec("t2")]
    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(return_value=MagicMock(content=""))
    resolver = IntentResolver(llm_client=mock_llm)
    result = await resolver.resolve("随便聊聊", all_tools)
    assert len(result) == 2  # 全部返回


@pytest.mark.asyncio
async def test_resolve_domain_filter_empty_fallback():
    """过滤后为空时兜底返回全部"""
    all_tools = [_make_spec("only_calendar", domain="calendar")]
    resolver = IntentResolver(llm_client=None)
    # "成绩" 匹配 analytics，但工具里没有 analytics domain
    result = await resolver.resolve("成绩分析", all_tools)
    assert len(result) == 1  # 兜底
```

- [ ] **Step 2: Implement IntentResolver**

```python
# src/edu_cloud/ai/intent_resolver.py
import re

DOMAIN_RULES: dict[str, list[str]] = {
    "exam": ["考试", "科目", "试卷", "exam", "subject", "paper"],
    "student": ["学生", "班级", "名单", "student", "class", "roster"],
    "analytics": ["成绩", "分数", "分析", "排名", "统计", "score", "rank", "stats"],
    "knowledge": ["知识点", "课标", "教材", "knowledge", "curriculum"],
    "bank": ["错题", "题库", "error book", "question bank"],
    "profile": ["画像", "趋势", "薄弱", "profile", "trend", "weakness"],
    "action": ["报告", "评语", "生成", "report", "comment", "generate"],
    "studio": ["文档", "论文", "document", "paper writing"],
    "calendar": ["日历", "校历", "通知", "calendar", "notification"],
}


class IntentResolver:
    def __init__(self, llm_client):
        self._patterns: dict[str, re.Pattern] = {}
        for domain, keywords in DOMAIN_RULES.items():
            escaped = [re.escape(k) for k in keywords]
            self._patterns[domain] = re.compile("|".join(escaped), re.IGNORECASE)
        self._llm = llm_client
        self.last_domains: list[str] = []

    def resolve_by_rules(self, message: str) -> list[str] | None:
        matched = []
        for domain, pattern in self._patterns.items():
            if pattern.search(message):
                matched.append(domain)
        return matched[:3] if matched else None

    async def resolve(self, message: str, available_tools: list) -> list:
        domains = self.resolve_by_rules(message)

        if domains is None and self._llm is not None:
            domains = await self._llm_classify(message)

        if not domains:
            self.last_domains = []
            return available_tools

        self.last_domains = domains
        selected = [t for t in available_tools if t.domain in domains]
        return selected if selected else available_tools

    async def _llm_classify(self, message: str) -> list[str]:
        prompt = (
            "你是意图分类器。根据用户消息，返回 1-3 个最相关的域。"
            f"可选域：{', '.join(DOMAIN_RULES.keys())}。"
            "只返回域名，用逗号分隔，不要其他内容。"
        )
        try:
            response = await self._llm.chat(
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": message},
                ],
            )
            text = response.content if hasattr(response, "content") else str(response)
            return [d.strip() for d in text.split(",") if d.strip() in DOMAIN_RULES]
        except Exception:
            return []
```

- [ ] **Step 3: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_intent_resolver.py -v`
Expected: 7 passed

- [ ] **Step 4: Commit**

```bash
git add src/edu_cloud/ai/intent_resolver.py tests/test_ai/test_intent_resolver.py
git commit -m "feat: add IntentResolver with rule-based + LLM fallback domain matching"
```

**审查清单:**
- ✓ 9 个 domain 的关键词完整覆盖中英文
- ✓ 规则无匹配时走 LLM fallback
- ✓ LLM 也失败时返回全部工具
- ✓ 过滤后为空时兜底返回全部
- ✗ 恶意输入（超长消息）不应导致正则引擎 ReDoS

**边界条件:**
- 空消息 "" → resolve_by_rules 返回 None → LLM 或全部
- 匹配所有 9 个 domain 的消息 → 只返回前 3 个
- available_tools=[] → 返回 []

---

### Task 6: ModelRouter + LLMSlot tier + LLM Factory

**Files:**
- Create: `src/edu_cloud/ai/model_router.py`
- Create: `src/edu_cloud/ai/llm_factory.py`
- Modify: `src/edu_cloud/core/models/llm_slot.py`
- Create: `tests/test_ai/test_model_router.py`

- [ ] **Step 1: Write failing tests for ModelRouter**

```python
# tests/test_ai/test_model_router.py
from edu_cloud.ai.model_router import ModelRouter
from edu_cloud.ai.registry import ToolSpec
from unittest.mock import AsyncMock


def _make_spec(name, risk_level="low", domain="general"):
    return ToolSpec(
        name=name, description="", parameters={}, func=AsyncMock(),
        risk_level=risk_level, domain=domain,
    )


def test_high_risk_selects_advanced():
    router = ModelRouter()
    tools = [_make_spec("danger", risk_level="high")]
    tier = router.select(["exam"], tools)
    assert tier == "advanced"


def test_three_domains_selects_advanced():
    router = ModelRouter()
    tools = [_make_spec("t1")]
    tier = router.select(["exam", "student", "analytics"], tools)
    assert tier == "advanced"


def test_complex_combo_selects_advanced():
    router = ModelRouter()
    tools = [_make_spec("t1")]
    tier = router.select(["analytics", "profile"], tools)
    assert tier == "advanced"


def test_default_selects_standard():
    router = ModelRouter()
    tools = [_make_spec("t1")]
    tier = router.select(["exam"], tools)
    assert tier == "standard"


def test_empty_domains_selects_standard():
    router = ModelRouter()
    tools = [_make_spec("t1")]
    tier = router.select([], tools)
    assert tier == "standard"
```

- [ ] **Step 2: Implement ModelRouter**

```python
# src/edu_cloud/ai/model_router.py
from edu_cloud.ai.registry import ToolSpec

_COMPLEX_COMBOS = [
    {"analytics", "profile"},
    {"analytics", "knowledge"},
]


class ModelRouter:
    def select(self, intent_domains: list[str], tools: list[ToolSpec]) -> str:
        if any(t.risk_level == "high" for t in tools):
            return "advanced"
        if len(intent_domains) >= 3:
            return "advanced"
        domain_set = set(intent_domains)
        if any(combo.issubset(domain_set) for combo in _COMPLEX_COMBOS):
            return "advanced"
        return "standard"
```

- [ ] **Step 3: Add tier to LLMSlot**

在 `src/edu_cloud/core/models/llm_slot.py` 的 LLMSlot 类中添加字段：
```python
tier: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
```

- [ ] **Step 4: Implement LLM factory**

```python
# src/edu_cloud/ai/llm_factory.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.ai.llm import LLMChatClient
from edu_cloud.config import settings
from edu_cloud.core.models.llm_slot import LLMSlot


async def create_llm_for_tier(
    tier: str, school_id: str | None, db: AsyncSession
) -> LLMChatClient:
    """按 tier 查询 LLMSlot，返回对应的 LLMChatClient"""
    # 优先：学校级 slot
    slot = None
    if school_id:
        stmt = select(LLMSlot).where(
            LLMSlot.school_id == school_id,
            LLMSlot.tier == tier,
            LLMSlot.is_enabled == True,
        ).limit(1)
        result = await db.execute(stmt)
        slot = result.scalar_one_or_none()

    # 其次：平台默认 slot
    if not slot:
        stmt = select(LLMSlot).where(
            LLMSlot.school_id == None,
            LLMSlot.tier == tier,
            LLMSlot.is_enabled == True,
        ).limit(1)
        result = await db.execute(stmt)
        slot = result.scalar_one_or_none()

    # 兜底：.env 配置
    if not slot:
        return LLMChatClient(
            api_url=settings.LLM_API_URL,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_DEFAULT_MODEL,
        )

    return LLMChatClient(
        api_url=slot.api_url,
        api_key=slot.api_key,
        model=slot.model,
        slot=slot.label or "",
    )
```

- [ ] **Step 5: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_model_router.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/ai/model_router.py src/edu_cloud/ai/llm_factory.py src/edu_cloud/core/models/llm_slot.py tests/test_ai/test_model_router.py
git commit -m "feat: add ModelRouter + LLM factory + LLMSlot tier field"
```

**审查清单:**
- ✓ ModelRouter 规则优先级清晰（high risk > 3域 > 复杂组合 > standard）
- ✓ LLM factory 三级 fallback（学校→平台→.env）
- ✓ LLMSlot.tier nullable 向后兼容
- ✗ create_llm_for_tier 在无任何 slot 且 .env 未配置时会抛异常

---

### Task 7: Agent Pipeline 集成

**Files:**
- Modify: `src/edu_cloud/api/ai.py`
- Modify: `src/edu_cloud/ai/agent.py`
- Create: `tests/test_ai/test_agent_pipeline.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_ai/test_agent_pipeline.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from edu_cloud.ai.tool_access import ToolAccessResolver
from edu_cloud.ai.intent_resolver import IntentResolver
from edu_cloud.ai.model_router import ModelRouter
from edu_cloud.ai.registry import ToolSpec


def _make_spec(name, domain="general", allowed_roles=None, module_code=None):
    return ToolSpec(
        name=name, description=f"Tool {name}", parameters={},
        func=AsyncMock(return_value={"ok": True}),
        domain=domain, allowed_roles=allowed_roles, module_code=module_code,
    )


@pytest.mark.asyncio
async def test_pipeline_end_to_end():
    """完整 Pipeline: 工具过滤 → 意图裁剪 → 模型选择"""
    all_tools = [
        _make_spec("get_scores", domain="analytics", allowed_roles=None),
        _make_spec("admin_tool", domain="exam", allowed_roles=["platform_admin"]),
        _make_spec("calendar_tool", domain="calendar"),
    ]

    # Step 1: ToolAccessResolver (subject_teacher 看不到 admin_tool)
    resolver = ToolAccessResolver()
    available = await resolver.resolve(
        all_specs=all_tools, role="subject_teacher",
        enabled_modules=set(), capabilities={},
    )
    assert len(available) == 2  # get_scores + calendar_tool

    # Step 2: IntentResolver (查成绩 → analytics domain)
    intent = IntentResolver(llm_client=None)
    selected = await intent.resolve("查一下成绩", available)
    assert len(selected) == 1
    assert selected[0].name == "get_scores"
    assert intent.last_domains == ["analytics"]

    # Step 3: ModelRouter (单域低风险 → standard)
    tier = ModelRouter().select(intent.last_domains, selected)
    assert tier == "standard"


@pytest.mark.asyncio
async def test_pipeline_parent_sees_only_profile():
    """parent 角色只能看到 profile 域工具"""
    all_tools = [
        _make_spec("get_scores", domain="analytics"),
        _make_spec("get_profile", domain="profile", allowed_roles=None),
        _make_spec("admin_tool", allowed_roles=["platform_admin"]),
    ]
    resolver = ToolAccessResolver()
    available = await resolver.resolve(
        all_specs=all_tools, role="parent",
        enabled_modules=set(), capabilities={},
    )
    # parent: allowed_roles=None 的工具都能看到
    assert len(available) == 2  # get_scores + get_profile


@pytest.mark.asyncio
async def test_pipeline_module_disabled():
    """模块禁用时工具不可见"""
    all_tools = [
        _make_spec("exam_tool", domain="exam", module_code="exam"),
        _make_spec("open_tool", domain="general"),
    ]
    resolver = ToolAccessResolver()
    available = await resolver.resolve(
        all_specs=all_tools, role="platform_admin",
        enabled_modules={"grading"},  # exam 未启用
        capabilities={},
    )
    assert len(available) == 1
    assert available[0].name == "open_tool"
```

- [ ] **Step 2: Modify agent.py — 删除 ROLE_TOOL_CATEGORIES，run() 接收 tools 参数**

在 `src/edu_cloud/ai/agent.py` 中：
1. 删除 `ROLE_TOOL_CATEGORIES` 字典
2. 在 `Agent.run()` 签名中添加 `tools: list[ToolSpec] | None = None` 参数
3. 如果 `tools` 提供，用它代替 `registry.get_schemas()`

- [ ] **Step 3: Modify ai.py — 插入 Pipeline**

在 `src/edu_cloud/api/ai.py` 的 `ai_chat()` 端点中，在 Agent.run() 调用前插入 Pipeline：
1. 导入 ToolAccessResolver, IntentResolver, ModelRouter, create_llm_for_tier, AgentProfileService
2. 用 Pipeline 替换现有的 `ROLE_TOOL_CATEGORIES` 工具过滤逻辑
3. 将 selected_tools 和 model_tier 传给 Agent

- [ ] **Step 4: Run integration tests + existing AI tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/ -v`
Expected: 全部 pass

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/ai/agent.py src/edu_cloud/api/ai.py tests/test_ai/test_agent_pipeline.py
git commit -m "feat: integrate Agent Pipeline (ToolAccess→Intent→ModelRouter) into ai_chat"
```

**审查清单:**
- ✓ ROLE_TOOL_CATEGORIES 已删除
- ✓ Pipeline 在 Agent.run() 之前执行
- ✓ 现有 AI 测试仍通过
- ✗ Pipeline 中任何步骤异常不应阻塞对话（应 fallback 到全工具集 + standard 模型）

---

### Task 8: 31 个工具元数据迁移

**Files:**
- Modify: `src/edu_cloud/ai/tools/analytics.py`
- Modify: `src/edu_cloud/ai/tools/analytics_score.py`
- Modify: `src/edu_cloud/ai/tools/analytics_compare.py`
- Modify: `src/edu_cloud/ai/tools/exams.py`
- Modify: `src/edu_cloud/ai/tools/students.py`
- Modify: `src/edu_cloud/ai/tools/bank.py`
- Modify: `src/edu_cloud/ai/tools/profile.py`
- Modify: `src/edu_cloud/ai/tools/knowledge.py`
- Modify: `src/edu_cloud/ai/tools/knowledge_db.py`
- Modify: `src/edu_cloud/ai/tools/actions.py`

- [ ] **Step 1: 为每个工具添加元数据**

按以下映射表为所有 31 个工具添加 `module_code`, `domain`, `allowed_roles`, `risk_level`：

| 文件 | 工具 | category(旧) | module_code | domain | allowed_roles | risk_level |
|------|------|-------------|-------------|--------|--------------|-----------|
| analytics.py | get_exam_scores | L2_cross_school | exam | analytics | ["platform_admin","district_admin"] | low |
| analytics.py | get_class_stats | L2_cross_school | exam | analytics | ["platform_admin","district_admin"] | low |
| analytics_score.py | exam_summary | L2_analytics | exam | analytics | ["platform_admin","academic_director","grade_leader"] | low |
| analytics_score.py | score_distribution | L2_analytics | exam | analytics | ["platform_admin","academic_director","grade_leader"] | low |
| analytics_score.py | question_analysis | L2_analytics | exam | analytics | ["platform_admin","academic_director","grade_leader"] | low |
| analytics_score.py | student_scores | L2_analytics | exam | analytics | ["platform_admin","academic_director","grade_leader"] | low |
| analytics_score.py | class_scores | L2_analytics | exam | analytics | ["platform_admin","academic_director","grade_leader"] | low |
| analytics_compare.py | compare_classes | L2_analytics | exam | analytics | ["platform_admin","academic_director","grade_leader"] | low |
| analytics_compare.py | rank_students | L2_analytics | exam | analytics | ["platform_admin","academic_director","grade_leader"] | low |
| analytics_compare.py | grade_aggregates | L2_analytics | exam | analytics | ["platform_admin","academic_director","grade_leader"] | low |
| exams.py | exam_list | L1_exam | exam | exam | None | low |
| exams.py | exam_detail | L1_exam | exam | exam | None | low |
| exams.py | subject_questions | L1_exam | exam | exam | None | low |
| students.py | class_list | L1_student | None | student | None | low |
| students.py | student_roster | L1_student | None | student | None | low |
| students.py | search_student | L1_student | None | student | None | low |
| students.py | student_profile | L1_student | None | student | None | low |
| bank.py | error_book | L5_bank | None | bank | None | low |
| bank.py | question_stats | L5_bank | None | bank | None | low |
| profile.py | score_trend | L6_profile | None | profile | None | low |
| profile.py | knowledge_map | L6_profile | None | profile | None | low |
| profile.py | weakness_diagnosis | L6_profile | None | profile | None | low |
| profile.py | error_pattern | L6_profile | None | profile | None | low |
| knowledge.py | search_curriculum | L3_knowledge | None | knowledge | None | low |
| knowledge.py | search_textbook | L3_knowledge | None | knowledge | None | low |
| knowledge.py | search_concept | L3_knowledge | None | knowledge | None | low |
| knowledge.py | search_gaokao | L3_knowledge | None | knowledge | None | low |
| knowledge_db.py | knowledge_tree | L3_knowledge_db | None | knowledge | None | low |
| knowledge_db.py | question_knowledge_points | L3_knowledge_db | None | knowledge | None | low |
| actions.py | generate_report | L4_action | None | action | ["platform_admin","academic_director","subject_teacher","homeroom_teacher"] | med |
| actions.py | generate_comment | L4_action | None | action | ["platform_admin","academic_director","subject_teacher","homeroom_teacher"] | med |

为每个 `@tools.register(...)` 添加新参数。例如：
```python
# 改前
@tools.register(
    name="get_exam_scores",
    description="...",
    parameters={...},
    category="L2_cross_school",
)

# 改后
@tools.register(
    name="get_exam_scores",
    description="...",
    parameters={...},
    category="L2_cross_school",
    module_code="exam",
    domain="analytics",
    allowed_roles=["platform_admin", "district_admin"],
    risk_level="low",
)
```

- [ ] **Step 2: Verify all 31 tools have metadata**

Run: `cd C:/Users/Administrator/edu-cloud && python -c "from edu_cloud.ai.tools import *; from edu_cloud.ai.registry import tools; specs = tools.get_all_specs(); missing = [s.name for s in specs if s.domain == 'general' and s.category != 'general']; print(f'Total: {len(specs)}, Missing domain: {missing}')""`

Expected: `Total: 31, Missing domain: []`

- [ ] **Step 3: Run all tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/ -v`
Expected: 全部 pass

- [ ] **Step 4: Commit**

```bash
git add src/edu_cloud/ai/tools/
git commit -m "feat: add module_code/domain/risk_level/allowed_roles metadata to all 31 tools"
```

**审查清单:**
- ✓ 31 个工具全部有 domain（非 "general"）
- ✓ allowed_roles 与原 ROLE_TOOL_CATEGORIES 映射一致
- ✓ module_code 与 SchoolModule.module_code 枚举一致
- ✓ category 字段保留（向后兼容）
- ✗ 工具名称拼写错误导致映射丢失

---

### Task 9: Alembic Migration + CLAUDE.md + 收尾

**Files:**
- Modify: `alembic/env.py`
- Modify: `tests/test_alembic_migration.py`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update alembic/env.py imports**

添加：
```python
import edu_cloud.models.agent_profile  # noqa: F401
```

- [ ] **Step 2: Generate migration**

Run: `cd C:/Users/Administrator/edu-cloud && alembic revision --autogenerate -m "add agent_profiles and agent_runs tables, llm_slots tier field"`

- [ ] **Step 3: Update test_alembic_migration.py**

在预期表集合中添加 `"agent_profiles"` 和 `"agent_runs"`。

- [ ] **Step 4: Update CLAUDE.md**

在数据模型概要中添加 agent_profiles 和 agent_runs 表。
在 AI Agent 架构段说明 Pipeline 流程。

- [ ] **Step 5: Run full test suite**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Expected: 全部 pass（~930+ tests）

- [ ] **Step 6: Commit**

```bash
git add alembic/ tests/test_alembic_migration.py CLAUDE.md
git commit -m "feat: add Alembic migration for agent_profiles/agent_runs + CLAUDE.md sync"
```

**审查清单:**
- ✓ Migration 包含 agent_profiles + agent_runs + llm_slots.tier
- ✓ test_alembic_migration 更新了预期表集合
- ✓ CLAUDE.md 同步了新模型和 API 架构变更
- ✗ Migration downgrade 应能干净回退
