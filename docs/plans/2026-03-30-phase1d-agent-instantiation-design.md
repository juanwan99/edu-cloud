# Phase 1d: Agent 核心基础设施设计

> **创建**: 2026-03-30 10:53:10
> **依赖**: Phase 1c (Capability + AuditLog) ✅
> **范围**: 纯后端，不含前端页面，不含常驻巡检（→ Phase 1e）
> **总设计**: `docs/plans/2026-03-29-business-logic-backfill-design.md` §3

---

## 1. 目标

将现有 AI Agent 从"flat 工具列表 + 硬编码角色映射"升级为"身份驱动 + 动态工具裁剪 + 模型分层路由"，使 Agent 具备：

1. **身份持久化**：每个用户拥有逻辑 Agent 实例，记录偏好和记忆摘要
2. **三重权限过滤**：RBAC ∩ 模块开关 ∩ Capability，替代 ROLE_TOOL_CATEGORIES
3. **意图驱动工具选择**：根据用户消息动态裁剪工具集（10-15 个），提高准确率
4. **成本优化模型路由**：按场景选择 mini/standard/advanced 模型

## 2. 现状分析

### 2.1 当前 Agent 架构

```
用户消息 → ai/agent.py ReAct 循环
  → ROLE_TOOL_CATEGORIES[role] → 按角色类别筛选工具（9 类别，31 tools 全暴露给角色）
  → 单一 LLM 模型（config.py LLM_DEFAULT_MODEL）
  → ai_sessions / ai_tool_calls 表记录
```

**问题**：
- `ROLE_TOOL_CATEGORIES` 是 Python dict 硬编码，管理员无法配置
- 所有匹配角色的工具全部传给 LLM（最多 31 个），工具选择准确率随数量下降
- 单模型策略：简单查询和复杂分析用同一模型，成本浪费
- 无 Agent 身份概念：用户每次对话是无状态的，无法积累偏好

### 2.2 Phase 1a-1c 已建设的基础

| 组件 | 提供能力 | Phase 1d 如何使用 |
|------|---------|------------------|
| SchoolModule | 模块开关（8 codes） | ToolAccessResolver 第二层过滤 |
| Capability | 域×操作×角色矩阵 | ToolAccessResolver 第三层过滤 |
| @audited | 变更审计 | Agent 配置变更自动审计 |
| ScopeFilter | 数据范围注入 | Agent 工具查询自动 scope |
| LLMSlot | 模型槽位管理 | ModelRouter 按 tier 选模型 |

## 3. 架构设计

### 3.1 整体流程

```
POST /api/v1/ai/chat
  │
  ├─ 1. get_or_create_profile(user_id, school_id)
  │     → AgentProfile（首次对话自动创建，后续复用）
  │
  ├─ 2. ToolAccessResolver.resolve(user_role, school_id, db)
  │     → RBAC 过滤 → Module 过滤 → Capability 过滤
  │     → 可用工具列表（如 20 个）
  │
  ├─ 3. IntentResolver.resolve(message, available_tools)
  │     → 规则引擎匹配 domain packs
  │     → 未匹配时 LLM fallback（mini 模型）
  │     → 裁剪后工具集（如 10 个）
  │
  ├─ 4. ModelRouter.select(intent_domains, tool_risk_levels)
  │     → 选择 LLMSlot tier（mini/standard/advanced）
  │
  ├─ 5. ReAct 循环（现有 agent.py 核心逻辑不变）
  │     → 用裁剪后工具集 + 选定模型执行
  │
  └─ 6. 记录 AgentRun（工具集/模型/域/token）
```

### 3.2 数据模型

#### AgentProfile（逻辑 Agent 身份）

```python
class AgentProfile(Base, IdMixin, TimestampMixin):
    __tablename__ = "agent_profiles"

    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    school_id: Mapped[UUID] = mapped_column(ForeignKey("schools.id"), index=True)
    profile_type: Mapped[str] = mapped_column(String(20), default="employee")
        # "employee" — 用户的个人 Agent
        # "system" — 系统级 Agent（预留，Phase 1e 巡检用）
    display_name: Mapped[str] = mapped_column(String(100))
    preferences: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
        # 用户偏好：{ "default_analysis_scope": "my_classes", "language": "zh" }
    memory_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
        # LLM 压缩的历史摘要（Phase 1e+ 使用）

    __table_args__ = (
        UniqueConstraint("owner_user_id", "school_id", name="uq_profile_user_school"),
    )
```

**设计决策**：
- 一个用户在一个学校只有一个 AgentProfile（UniqueConstraint）
- profile_type 区分员工级和系统级，为 Phase 1e 巡检预留
- preferences 和 memory_summary 为 JSON/Text，灵活扩展
- 不存储权限——权限从 UserRole + Capability 实时计算

#### AgentRun（每轮对话执行记录）

```python
class AgentRun(Base, IdMixin):
    __tablename__ = "agent_runs"

    profile_id: Mapped[UUID] = mapped_column(ForeignKey("agent_profiles.id"), index=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
        # 关联 ai_sessions 表（现有字段是 str 不是 FK）
    tools_resolved: Mapped[list] = mapped_column(JSON)
        # ToolAccessResolver 输出的工具名列表
    tools_selected: Mapped[list] = mapped_column(JSON)
        # IntentResolver 裁剪后的工具名列表
    model_used: Mapped[str] = mapped_column(String(50))
    model_tier: Mapped[str] = mapped_column(String(20))
        # "mini" | "standard" | "advanced"
    intent_domains: Mapped[list] = mapped_column(JSON)
        # IntentResolver 识别的 domain packs
    token_input: Mapped[int] = mapped_column(default=0)
    token_output: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

**设计决策**：
- session_id 用 String 关联而非 FK（兼容现有 ai_sessions 的 session_id 字段类型）
- 分别记录 tools_resolved 和 tools_selected，用于分析工具裁剪效果
- token 统计为后续成本分析提供数据

### 3.3 ToolSpec 元数据升级

在现有 `@registry.register()` 装饰器上扩展参数。

> **现有签名**（registry.py）：`register(self, name, description, parameters, category="general")`
> 返回包含 `{"name", "description", "parameters", "category", "func"}` 的 dict。
> **改造**：引入 `ToolSpec` dataclass 替代 dict，`register()` 新增可选参数，旧参数 `category` 保留向后兼容。

```python
@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict
    func: Callable
    category: str = "general"          # 保留，向后兼容
    module_code: str | None = None     # 新增：对应 SchoolModule.module_code
    domain: str = "general"            # 新增：IntentResolver domain pack
    requires_capabilities: list[tuple[str, str]] = field(default_factory=list)  # 新增
    risk_level: str = "low"            # 新增：low/med/high
    allowed_roles: list[str] | None = None  # 新增：None=不限角色

# 使用示例
@registry.register(
    name="get_exam_scores",
    description="...",
    parameters={...},
    module_code="exam",
    domain="analytics",
    requires_capabilities=[],
    risk_level="low",
    allowed_roles=None,
)
```

**元数据字段说明**：

| 字段 | 类型 | 用途 | 默认值 |
|------|------|------|--------|
| `module_code` | str | ToolAccessResolver 模块过滤 | None（不受模块开关限制） |
| `domain` | str | IntentResolver 域分组 | "general" |
| `requires_capabilities` | list[tuple] | Capability 检查，如 `[("exam", "read")]` | []（不需要额外 capability） |
| `risk_level` | str | ModelRouter 模型升级判据 | "low" |
| `allowed_roles` | list[str] \| None | RBAC 过滤，None 表示不限 | None |

**迁移路径**：
- 现有 31 个工具逐个添加元数据（从 ROLE_TOOL_CATEGORIES 反向推导 allowed_roles）
- ROLE_TOOL_CATEGORIES dict 删除
- ToolRegistry 内部 ToolSpec dataclass 新增上述字段

### 3.4 ToolAccessResolver

```python
class ToolAccessResolver:
    """三重过滤：RBAC → Module → Capability"""

    async def resolve(
        self, user_role: UserRole, school_id: UUID, db: AsyncSession
    ) -> list[ToolSpec]:
        all_tools = registry.get_all()
        result = []

        # 预加载：该校启用的模块 + capability 矩阵
        enabled_modules = await get_enabled_modules(db, school_id=school_id)
        capabilities = await get_capabilities(db, school_id=school_id, role=user_role.role)

        for tool in all_tools:
            # 层 1: RBAC
            if tool.allowed_roles is not None and user_role.role not in tool.allowed_roles:
                continue

            # 层 2: Module
            if tool.module_code and tool.module_code not in enabled_modules:
                continue

            # 层 3: Capability
            if not self._check_capabilities(tool.requires_capabilities, capabilities):
                continue

            result.append(tool)

        return result

    def _check_capabilities(self, required: list[tuple], caps: dict) -> bool:
        """所有 required capabilities 必须 enabled"""
        for domain, action in required:
            key = (domain, action)
            if key in caps and not caps[key]:
                return False
        return True  # 未配置的 capability 默认允许（宽松策略，与 Phase 1c 一致）
```

**设计决策**：
- 宽松策略：未在 capabilities 表中的条目默认允许（与 Phase 1c `check_capability` 一致）
- 预加载模块和 capability，避免 N+1 查询
- 返回 ToolSpec 对象（不是名称字符串），保留元数据供后续使用

### 3.5 IntentResolver（规则 + LLM 后备）

> **与现有代码的集成点**：IntentResolver 不直接调用 LLMChatClient.chat()（该方法不支持 tier 参数）。
> 而是接收一个已配置好 mini 模型的 LLMChatClient 实例。详见 §3.7 集成方案。

```python
# 规则引擎：关键词 → domain packs
DOMAIN_RULES: dict[str, list[str]] = {
    "exam":      ["考试", "科目", "试卷", "exam", "subject", "paper"],
    "student":   ["学生", "班级", "名单", "student", "class", "roster"],
    "analytics": ["成绩", "分数", "分析", "排名", "统计", "score", "rank", "stats"],
    "knowledge": ["知识点", "课标", "教材", "knowledge", "curriculum"],
    "bank":      ["错题", "题库", "error", "question bank"],
    "profile":   ["画像", "趋势", "薄弱", "profile", "trend", "weakness"],
    "action":    ["报告", "评语", "生成", "report", "comment", "generate"],
    "studio":    ["文档", "论文", "document", "paper writing"],
    "calendar":  ["日历", "校历", "通知", "calendar", "notification"],
}

class IntentResolver:
    def __init__(self, llm_client: LLMChatClient):
        self._rules = self._compile_rules(DOMAIN_RULES)
        self._llm = llm_client
        self.last_domains: list[str] = []  # 保存最近一次解析结果，供 ModelRouter 使用

    def resolve_by_rules(self, message: str) -> list[str] | None:
        """返回匹配的 1-3 个 domain，无匹配返回 None"""
        matched = []
        for domain, pattern in self._rules.items():
            if pattern.search(message):
                matched.append(domain)
        return matched[:3] if matched else None

    async def resolve(
        self, message: str, available_tools: list[ToolSpec]
    ) -> list[ToolSpec]:
        # 步骤 1: 规则匹配
        domains = self.resolve_by_rules(message)

        # 步骤 2: 未匹配 → LLM fallback
        if domains is None:
            domains = await self._llm_classify(message)

        # 步骤 3: 如果仍无结果 → 返回全部工具（不裁剪）
        if not domains:
            self.last_domains = []
            return available_tools

        self.last_domains = domains

        # 步骤 4: 按 domain 过滤
        selected = [t for t in available_tools if t.domain in domains]

        # 安全兜底：如果过滤后为空（规则/LLM 误判），返回全部
        return selected if selected else available_tools

    async def _llm_classify(self, message: str) -> list[str]:
        """调用 mini 模型进行意图分类。
        注意：self._llm 是已配置为 mini 模型的 LLMChatClient 实例，
        不需要传 model_tier 参数。"""
        prompt = (
            "你是意图分类器。根据用户消息，返回 1-3 个最相关的域。"
            f"可选域：{', '.join(DOMAIN_RULES.keys())}。"
            "只返回域名，用逗号分隔，不要其他内容。"
        )
        # self._llm 已绑定 mini 模型（在 ai.py 中初始化时指定）
        from edu_cloud.ai.schemas import ChatMessage

        response = await self._llm.chat(
            messages=[
                ChatMessage(role="system", content=prompt),
                ChatMessage(role="user", content=message),
            ],
        )
        # response 是 ChatMessage，取 content
        text = response.content if hasattr(response, 'content') else str(response)
        return [d.strip() for d in text.split(",") if d.strip() in DOMAIN_RULES]
```

**设计决策**：
- 规则引擎用预编译正则，O(1) 查找
- LLM fallback 使用 mini tier，max_tokens=50（最小消耗）
- 双兜底：LLM 也失败时返回全部工具（不会比现状差）
- 过滤后为空也返回全部（防误判导致功能丧失）

### 3.6 ModelRouter（模型分层路由）

```python
class ModelRouter:
    """根据意图和工具风险等级选择模型 tier"""

    def select(self, intent_domains: list[str], tools: list[ToolSpec]) -> str:
        """返回 LLMSlot tier: "mini" | "standard" | "advanced" """
        # 规则 1: 包含高风险工具 → advanced
        if any(t.risk_level == "high" for t in tools):
            return "advanced"

        # 规则 2: 跨域分析（>2 个 domain）→ advanced
        if len(intent_domains) >= 3:
            return "advanced"

        # 规则 3: 复杂域组合 → advanced
        complex_combos = [{"analytics", "profile"}, {"analytics", "knowledge"}]
        domain_set = set(intent_domains)
        if any(combo.issubset(domain_set) for combo in complex_combos):
            return "advanced"

        # 默认 → standard
        return "standard"
```

**与 LLMSlot 集成**：
- LLMSlot 现有字段（`src/edu_cloud/core/models/llm_slot.py`）：`slot_number`, `api_url`, `api_key`, `model`, `is_enabled`, `school_id`
- 新增字段：`tier` (String(20), nullable, 索引) — "mini" / "standard" / "advanced"
- 向后兼容：tier 为 null 的 slot 视为 "standard"

**LLM 客户端多实例方案**（解决 LLMChatClient 不支持 tier 参数的问题）：
- 不修改 LLMChatClient.chat() 签名
- 在 ai.py 的 ai_chat() 端点中，根据 ModelRouter 决策创建不同配置的 LLMChatClient 实例
- IntentResolver 接收一个专用的 mini 模型 LLMChatClient 实例
- Agent ReAct 循环接收 standard 或 advanced 模型的 LLMChatClient 实例
- 具体做法：新增 `_create_llm_for_tier(tier, school_id, db)` 工厂函数，按 tier 查询 LLMSlot

### 3.7 Agent 集成（ai.py + agent.py 修改）

**改动最小化原则**：ReAct 循环核心逻辑（agent.py Agent.run()）不变，在 ai.py 的 ai_chat() SSE 端点中插入 Pipeline。

> **现有架构**：ai.py 中 `ai_chat()` 是 FastAPI SSE 端点，内部创建 `Agent()` 实例并调用 `agent.run()`。
> agent.py 中 `Agent.run()` 接收 tools、session_id 等参数执行 ReAct 循环。
> 改动点在 ai.py 的 ai_chat() 中，在调用 Agent.run() 之前插入 Pipeline。

```python
# ai.py 中 ai_chat() 端点改造
async def ai_chat(request: Request, ...):
    user = ...  # 现有 JWT 认证
    role_obj = ...  # 现有角色解析

    # === 新增：Agent Pipeline ===
    # 1. 获取/创建 Agent 身份
    profile = await get_or_create_profile(user.id, role_obj.school_id, db)

    # 2. 三重权限过滤
    resolver = ToolAccessResolver()
    available_tools = await resolver.resolve(role_obj, role_obj.school_id, db)

    # 3. 意图驱动工具裁剪
    llm_mini = await _create_llm_for_tier("mini", role_obj.school_id, db)
    intent_resolver = IntentResolver(llm_mini)
    selected_tools = await intent_resolver.resolve(message, available_tools)

    # 4. 模型路由
    model_tier = ModelRouter().select(intent_resolver.last_domains, selected_tools)
    llm_for_agent = await _create_llm_for_tier(model_tier, role_obj.school_id, db)
    # === Pipeline 结束 ===

    # 现有 ReAct 循环，但用 selected_tools 和选定模型
    agent = Agent(llm_for_agent, registry)
    async for event in agent.run(
        message, session_id, db, role_obj.school_id, ...,
        tools=selected_tools,  # 替代原有的 registry.get_all()
    ):
        yield event

    # === 新增：记录 AgentRun ===
    await create_agent_run(profile.id, session_id, ...)
```

### 3.8 ROLE_TOOL_CATEGORIES 迁移映射

现有 9 类别到新元数据的映射（确保不丢失权限）：

| 旧类别 | 旧角色 | 新 allowed_roles | 新 domain |
|--------|--------|-----------------|-----------|
| L1_exam | 全部 | None（不限） | exam |
| L1_student | 全部 | None | student |
| L2_analytics | academic_director+ | [platform_admin, academic_director, grade_leader] | analytics |
| L2_cross_school | platform_admin, district_admin | [platform_admin, district_admin] | analytics |
| L3_knowledge | 全部 | None | knowledge |
| L3_knowledge_db | 全部 | None | knowledge |
| L4_action | subject_teacher+ | [platform_admin, academic_director, subject_teacher, homeroom_teacher] | action |
| L5_bank | 全部 | None | bank |
| L6_profile | 全部 | None | profile |

**验证方法**：迁移后跑现有 3 个 AI 测试（test_ai/），确保角色-工具映射不变。

## 4. 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| Create | `src/edu_cloud/models/agent_profile.py` | AgentProfile + AgentRun ORM |
| Create | `src/edu_cloud/ai/tool_access.py` | ToolAccessResolver |
| Create | `src/edu_cloud/ai/intent_resolver.py` | IntentResolver（规则+LLM） |
| Create | `src/edu_cloud/ai/model_router.py` | ModelRouter |
| Create | `src/edu_cloud/services/agent_profile_service.py` | Profile CRUD + get_or_create |
| Modify | `src/edu_cloud/ai/registry.py` | ToolSpec 扩展元数据字段 |
| Modify | `src/edu_cloud/ai/agent.py` | 集成 Pipeline（入口插入） |
| — | `src/edu_cloud/ai/llm.py` | 不修改（chat() 签名不变） |
| Modify | `src/edu_cloud/ai/tools/*.py` | 31 个工具添加元数据 |
| Create | `src/edu_cloud/ai/llm_factory.py` | _create_llm_for_tier() 工厂函数 |
| Modify | `src/edu_cloud/core/models/llm_slot.py` | LLMSlot 添加 tier 字段 |
| Modify | `alembic/env.py` | 导入新模型 |
| Modify | `tests/conftest.py` | 导入新模型 |
| Modify | `tests/test_alembic_migration.py` | 更新表集合 |
| Modify | `CLAUDE.md` | 同步模型和架构变更 |

## 5. 测试策略

| 组件 | 测试重点 | 预估测试数 |
|------|---------|-----------|
| AgentProfile model | CRUD、唯一约束、get_or_create 幂等 | 4 |
| ToolAccessResolver | 三重过滤各层独立测试 + 组合测试 + 空工具集兜底 | 8 |
| IntentResolver 规则 | 各 domain 关键词命中 + 多域匹配 + 无匹配走 LLM | 6 |
| IntentResolver LLM | mock LLM 返回 + 解析失败兜底 | 3 |
| ModelRouter | tier 选择逻辑：高风险/跨域/默认 | 4 |
| Agent 集成 | 端到端（mock LLM）：角色→工具→域→模型完整流程 | 3 |
| 迁移回归 | ROLE_TOOL_CATEGORIES 删除后现有 AI 测试仍通过 | 3（现有） |
| Alembic | 新表迁移 smoke test | 1 |

**预估总计**: ~32 新测试

## 6. 风险与缓解

| 风险 | 级别 | 缓解 |
|------|------|------|
| IntentResolver 规则覆盖率不足 | MED | LLM fallback + 全工具集兜底，永远不会比现状差 |
| LLMSlot tier 字段迁移影响现有 slot | LOW | tier 默认 null 视为 standard，向后兼容 |
| 31 个工具元数据迁移遗漏 | MED | 迁移后 Grep 确认无工具缺少 module_code/domain |
| Agent Pipeline 增加延迟 | LOW | ToolAccessResolver 是纯 DB 查询（~5ms），IntentResolver 规则匹配 <1ms |

## 7. 不在范围内

- 常驻巡检 Agent（→ Phase 1e）
- Agent 管理前端页面（→ 后续 Phase）
- Agent 记忆持久化/压缩（memory_summary 字段预留，逻辑不实现）
- 对话历史摘要（context.py 现有裁剪逻辑不变）

## 8. GPT 审查待处置项

> Plan Review R2 design-concern，不阻塞执行，后续迭代处理。

- **F-01**: design §3.8 迁移映射表中 L1_exam/L1_student/L3/L5 的 allowed_roles 应与 plan 一致（排除 parent）。当前 design 仍写 None，plan 已修正为显式列表。执行时以 plan 为准。
- **N-03**: Pipeline 选出 selected_tools 后，需同步重建 AgentContext.system_content 中的 tool_names 列表，否则多轮会话中 system prompt 和实际可用工具不一致。
- **N-04**: llm.py 无需修改签名，File Map 中"修改 llm.py"应改为"不修改 llm.py"，真正新增的是 llm_factory.py。
