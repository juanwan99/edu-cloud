# edu-cloud AI Agent 系统性重构设计 v2

> 状态：设计定稿（Claude + GPT 5.5 五轮辩论 + 用户两次纠正）
> 日期：2026-05-12
> 范围：AI Agent 子系统全面重构，锚定 Pydantic AI 为引擎层
> 前置文档：v1（场景路由方案）已废弃

---

## 1. 核心定位

**一句话：用 Pydantic AI 做引擎，edu-cloud 做教育安全壳。**

- **Pydantic AI** 提供：agent loop、模型调用、工具 schema、RunContext 依赖注入、重试、流式输出、deferred tools
- **edu-cloud** 自建：RBAC 三层过滤、DataScope 数据隔离、写操作确认、预算控制、Artifact 脱敏、Trace 审计、跨会话记忆、教育领域知识

类比：Pydantic AI 之于 edu-cloud Agent，就像 FastAPI 之于 edu-cloud 后端——框架提供 HTTP/路由/校验，业务提供权限/数据/领域逻辑。

---

## 2. 设计原则

| 原则 | 约束 |
|------|------|
| **通用智能体** | 一个 agent 拥有全部已授权工具，自己判断该用什么，不做场景路由 |
| **框架为底座** | Pydantic AI 做引擎层，不自研 agent loop / LLM 调用 / 工具 schema |
| **特色为护城河** | 安全、数据治理、确认、审计、领域知识是 edu-cloud 自建的差异化 |
| **不欠技术债** | 一步到位原生重写，不做 wrapper / bridge / 双引擎共存 |
| **安全不信任框架** | Pydantic AI 是引擎不是安全边界，安全层由 edu-cloud 独立强制 |
| **权限硬边界** | RBAC + DataScope + Module 三层 fail-closed |
| **读自动写确认** | 只读工具自动执行，写工具暂停等教师确认 |
| **预算兜底** | 请求级硬限 + 用户/学校级配额，超限输出中间结果 |
| **PII 不出工具** | 学生姓名/成绩不进模型上下文/SSE/trace，统一走 Artifact 脱敏 |

---

## 3. 目标架构

```
FastAPI /api/ai/chat (SSE)
POST   /api/ai/runs/{run_id}/confirmations/{id}
      │
      ▼
┌─────────────────────────────────────────┐
│         EduAgentRuntime                  │
│  ┌─ 认证 / 角色 / 学校上下文             │
│  ├─ 构建 AgentDeps                      │
│  ├─ RBAC 过滤 → 构建 allowed tools       │
│  ├─ 构建 system prompt + 记忆上下文       │
│  ├─ 运行 Pydantic AI Agent               │
│  └─ 翻译 Pydantic 事件 → 现有 SSE 格式   │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│     Pydantic AI 引擎层（框架提供）        │
│                                          │
│  Agent Loop（plan → act → observe）      │
│  RunContext[AgentDeps]                    │
│  @agent.tool 原生工具定义                 │
│  Deferred Tools（写暂停）                 │
│  UsageLimits（请求级模型调用限制）         │
│  ModelRetry（工具失败重试）                │
│  Typed Output（Pydantic 输出校验）         │
│                                          │
│  OpenAIProvider                           │
│  └─ AsyncOpenAI(base_url=localhost:8100)  │
│     + X-LLM-Slot header → llm-proxy      │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│     edu-cloud 特色层（自建护城河）        │
│                                          │
│  PolicyToolGuardrail                      │
│  ├─ 注册期：只暴露 RBAC 允许的工具         │
│  ├─ 调用前：before_tool() 硬检查          │
│  └─ 调用后：after_tool() 审计+artifact    │
│                                          │
│  DataScope（查询层强制注入 WHERE）         │
│  AgentBudget（token/工具/写操作/wall-clock）│
│  ConfirmationBroker（写确认 SSE+REST）    │
│  ArtifactManager（大结果脱敏摘要）         │
│  TraceRecorder（结构化决策记录）            │
│  MemoryStore（跨会话实体记忆）             │
│  StudentAnonymizer（PII 保护）            │
│  教育领域 System Prompt（方法论注入）      │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│     数据层                               │
│                                          │
│  async_sessionmaker（每工具独立 session）  │
│  DataScope scoped queries                 │
│  ai_artifacts / ai_agent_trace 表         │
│  ai_budget_usage_daily / policy 表        │
│  ai_confirmations 表                      │
└─────────────────────────────────────────┘
```

### 退役的旧组件

| 旧组件 | 替代 | 处置 |
|--------|------|------|
| `AgentLoop` | Pydantic AI Agent Loop | 删除 |
| `Supervisor` | 不需要（通用 agent 无分发） | 删除 |
| `ToolRegistry` | Pydantic AI `@agent.tool` + `EduToolCatalog` | 删除 |
| `ToolOrchestrator` | Pydantic AI 工具执行 + `PolicyToolGuardrail` | 删除 |
| `LLMProxyAdapter` | `OpenAIProvider(base_url=...)` | 删除 |
| `IntentRouter` | 不需要（agent 自己判断） | 删除 |
| `ModelRouter` | `AgentDeps.model_slot` + OpenAI client header | 删除 |
| `CapabilityProbe` | Pydantic AI `UsageLimits` + `AgentBudget` preset | 简化 |
| `AgentTeam` / `TeamExecutor` | 不需要（单 agent） | 删除 |
| `ToolContext` | `AgentDeps`（替代，不包含） | 删除 |

### 保留增强的组件

| 组件 | 处置 |
|------|------|
| `DataScope` / `DataScopeBuilder` | 保留，注入 AgentDeps |
| `MemoryStore` / `MemoryInjector` / `MemoryExtractor` | 保留增强 |
| `OutputValidator` → Pydantic output model | 重写 |
| `SensitivityRouter` | 保留，决定 model_slot |
| `Anonymizer` | 保留，注入 AgentDeps |
| `AuditLogger` → `TraceRecorder` | 重写 |
| 63 个工具的业务逻辑 | 保留，重写注册方式 |

---

## 4. Pydantic AI 集成细节

### 4.1 llm-proxy 对接

```python
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

def build_model(slot: str) -> OpenAIModel:
    client = AsyncOpenAI(
        base_url="http://localhost:8100/v1",
        api_key="unused",
        default_headers={"X-LLM-Slot": slot},
    )
    return OpenAIModel(
        "edu-cloud-agent",
        provider=OpenAIProvider(openai_client=client),
    )
```

### 4.2 Agent 构建

```python
from pydantic_ai import Agent

agent = Agent(
    model=build_model(deps.model_slot),
    deps_type=AgentDeps,
    tools=[tool.fn for tool in allowed_tools],
    system_prompt=system_prompt,
    output_type=TeacherAnswer,
)

result = await agent.run(
    user_message,
    deps=agent_deps,
    message_history=history,
    usage_limits=UsageLimits(
        request_limit=budget.request_limit,
        request_tokens_limit=budget.request_token_limit,
    ),
)
```

### 4.3 多轮对话

```python
result2 = await agent.run(
    new_message,
    deps=agent_deps,
    message_history=result1.new_messages(),
)
```

### 4.4 流式输出

```python
async with agent.run_stream(user_message, deps=deps) as stream:
    async for event in stream.stream_text():
        yield sse_format(event)
```

---

## 5. edu-cloud 特色层设计

### 5.1 AgentDeps（替代旧 ToolContext）

```python
@dataclass(slots=True)
class AgentDeps:
    # 身份
    run_id: str
    request_id: str
    session_id: str
    user_id: str
    school_id: str
    role: str

    # 权限
    data_scope: DataScope
    enabled_modules: frozenset[str]
    capabilities: Mapping[tuple[str, str], bool]

    # 基础设施
    db_sessionmaker: async_sessionmaker[AsyncSession]
    budget: AgentBudget
    policy: PolicyToolGuardrail
    confirmations: ConfirmationBroker
    artifacts: ArtifactManager
    trace: TraceRecorder
    memory: MemoryStore
    anonymizer: StudentAnonymizer

    # 模型
    model_slot: str
```

**关键设计决策：** `db_sessionmaker` 而非 `db: AsyncSession`。每个工具调用创建独立 session，解决旧架构中共享 session 导致并行被禁用的问题。

### 5.2 EduToolMeta（工具元数据）

```python
@dataclass(frozen=True)
class EduToolMeta:
    name: str
    module_code: str
    domain: str
    risk_level: Literal["low", "medium", "high", "critical"]
    is_read_only: bool
    allowed_roles: frozenset[str]
    requires_capabilities: frozenset[tuple[str, str]]
    sensitivity: Literal["public", "school", "class", "student", "pii"]
    artifact_policy: Literal["inline", "auto", "always"]
```

### 5.3 PolicyToolGuardrail（三层硬边界）

```
注册期：只把 RBAC 允许的工具交给 Pydantic AI Agent
调用前：before_tool() — RBAC/DataScope/Budget/risk/确认 token
查询层：所有业务查询必须接受 DataScope，禁止裸 school_id
调用后：after_tool() — 结果大小/PII/artifact 化/预算扣减/trace
```

```python
class PolicyToolGuardrail:
    async def before_tool(
        self, meta: EduToolMeta, args: dict
    ) -> ToolCallRecord:
        """每个工具调用前的硬检查。失败直接拒绝，不给模型重试。"""
        self._check_role(meta)
        self._check_module(meta)
        self._check_capability(meta)
        self._check_data_scope(meta, args)
        self._check_budget(meta)
        self._check_duplicate_failure(meta, args)
        if not meta.is_read_only:
            self._require_confirmation_token(meta, args)
        return ToolCallRecord(...)

    async def after_tool(
        self, call: ToolCallRecord, result: Any
    ) -> Any:
        """调用后：审计、artifact 化、预算扣减。"""
        self._budget_debit(call)
        self._trace_record(call, result)
        return await self._maybe_artifact(call, result)
```

### 5.4 ConfirmationBroker（写操作确认）

利用 Pydantic AI 的 **deferred tools** 机制：

```
1. Pydantic AI 选择写工具
2. 工具被标记为 deferred → AgentRuntime 收到 DeferredToolRequests
3. SSE 发 confirmation_required 事件
4. 前端展示确认卡（影响范围 + 批准/拒绝）
5. 教师 POST /api/ai/runs/{run_id}/confirmations/{id}
6. 后端校验 → agent.run(..., deferred_tool_results=...)
7. 继续执行
```

SSE 事件：

```json
{
  "type": "confirmation_required",
  "data": {
    "confirmation_id": "conf_xxx",
    "run_id": "run_xxx",
    "tool_name": "add_conduct_points",
    "risk_level": "medium",
    "title": "确认批量添加操行积分",
    "summary": "将为高一(3)班 48 名学生添加 +2 分（按时交作业）",
    "expires_at": "2026-05-12T10:35:00+08:00"
  }
}
```

确认端点：

```
POST /api/v1/ai/runs/{run_id}/confirmations/{confirmation_id}
Body: { "decision": "approve" | "reject", "idempotency_key": "...", "comment": "可选" }
```

超时 5 分钟，超时后返回"操作未执行，可重新发起"。

### 5.5 AgentBudget（预算控制）

```python
class AgentBudget(BaseModel):
    # 请求级硬限制
    request_token_limit: int
    request_limit: int          # 模型调用次数
    max_tool_calls: int
    max_write_ops: int
    max_wall_clock_ms: int

    # 运行时计数
    current_tokens: int = 0
    current_tool_calls: int = 0
    current_write_ops: int = 0
    started_at: datetime = Field(default_factory=datetime.now)

    # 用户/学校级配额（P1）
    user_daily_tokens_remaining: int | None = None
    school_daily_tokens_remaining: int | None = None
```

默认 preset：

| Tier | request_limit | tokens | tool_calls | write_ops | wall_clock |
|------|-------------|--------|-----------|----------|-----------|
| advanced | 25 | 80,000 | 40 | 3 | 180s |
| standard | 15 | 40,000 | 25 | 2 | 120s |
| basic | 8 | 16,000 | 12 | 1 | 60s |

Pydantic AI `UsageLimits` 管模型调用硬上限，edu-cloud `AgentBudget` 管工具/写操作/数据量。

### 5.6 ArtifactManager

```sql
CREATE TABLE ai_artifacts (
    id SERIAL PRIMARY KEY,
    artifact_id VARCHAR(64) NOT NULL UNIQUE,
    run_id VARCHAR(64),
    session_id VARCHAR(64),
    school_id INTEGER NOT NULL,
    owner_user_id INTEGER NOT NULL,
    source_tool VARCHAR(100),
    kind VARCHAR(30),           -- table / chart_data / report / diagnosis
    pii_level VARCHAR(10),      -- none / school / student
    row_count INTEGER,
    byte_size INTEGER,
    summary_json JSONB NOT NULL,
    preview_json JSONB,         -- 脱敏预览
    storage_uri TEXT,
    data_scope_hash VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ,
    INDEX(school_id, created_at)
);
```

**Artifact 化规则：**

| 条件 | 处理 |
|------|------|
| ≤ 32KB 且 ≤ 50 行且无学生明细 | 直接注入模型上下文 |
| > 32KB 或 > 50 行 | 落 artifact，模型只拿 summary + ID |
| 含学生级 PII/成绩 | 强制 artifact + 脱敏 preview |

模型看到的不是原始数据，而是：

```json
{
  "summary": {"student_count": 486, "avg_score": 78.2, "weak_points": ["函数应用"]},
  "preview": [{"student": "学生#A13", "score_band": "60-70"}],
  "artifact_id": "art_xxx",
  "available_operations": ["aggregate", "filter", "compare"]
}
```

### 5.7 TraceRecorder

```sql
CREATE TABLE ai_agent_trace (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL UNIQUE,
    session_id VARCHAR(64) NOT NULL,
    school_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role VARCHAR(50),
    tier VARCHAR(20),
    model_slot VARCHAR(30),
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    status VARCHAR(20),
    budget_initial JSONB,
    budget_final JSONB
);

CREATE TABLE ai_agent_trace_event (
    id SERIAL PRIMARY KEY,
    trace_id INTEGER REFERENCES ai_agent_trace(id),
    seq INTEGER NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    event_type VARCHAR(30) NOT NULL,
    tool_name VARCHAR(100),
    summary TEXT,
    reason_code VARCHAR(50),
    args_ref VARCHAR(64),       -- fingerprint, not raw
    result_ref VARCHAR(64),     -- artifact_id or fingerprint
    budget_snapshot JSONB,
    latency_ms INTEGER,
    pii_level VARCHAR(10)
);
```

**必记事件：** run_start / tool_call / tool_result / deferred / confirm / budget / artifact / output_validate / run_end / error

**PII 规则：** 学生姓名不入 trace，ID 用校级 salt hash，成绩只记区间。

### 5.8 教育领域 System Prompt

```python
DOMAIN_KNOWLEDGE = """
## 教学领域知识

### 备课教研
当教师询问备课相关问题时，通常需要：
1. 查看班级学生的薄弱知识点
2. 对照课标要求和教材内容
3. 参考高考真题和出题趋势
4. 基于以上数据生成教学建议

### 考后分析
当教师询问考试结果时，通常需要：
1. 获取整体概览和成绩分布
2. 分析题目得分率和错因
3. 班级对比和学生排名
4. 识别临界生和薄弱知识点
5. 生成可操作的分析报告

### 学生追踪
当教师关注某个学生时，可以并行查询：
成绩趋势 / 知识掌握 / 错题本 / 操行记录 / 作业完成

### 数据引用
- 所有数据结论必须来自工具查询结果，不可臆造
- 涉及学生个人信息时使用代号，不展示真实姓名
- 数值结论标注数据来源工具名
"""
```

---

## 6. 工具迁移模式

### 6.1 迁移前（旧模式）

```python
@tools.register(
    name="get_exam_scores",
    description="获取考试成绩",
    parameters={...},
    category="analytics",
    module_code="exam",
    allowed_roles=["teacher", "dean"],
    is_read_only=True,
    sensitivity="student",
)
async def get_exam_scores(input: dict, ctx: ToolContext) -> ToolResult:
    exam_id = input.get("exam_id")
    # 手写 scope 过滤
    query = select(Score).where(
        Score.school_id == ctx.school_id,
        Score.class_id.in_(ctx.class_ids or []),
    )
    async with ctx.db.begin():
        rows = (await ctx.db.execute(query)).all()
    return ToolResult(success=True, data=[...])
```

### 6.2 迁移后（Pydantic AI 原生）

```python
GET_EXAM_SCORES_META = EduToolMeta(
    name="get_exam_scores",
    module_code="exam",
    domain="analytics",
    risk_level="low",
    is_read_only=True,
    allowed_roles=frozenset({"teacher", "academic_director", "grade_leader"}),
    requires_capabilities=frozenset(),
    sensitivity="student",
    artifact_policy="auto",
)

@agent.tool(name="get_exam_scores")
async def get_exam_scores(
    ctx: RunContext[AgentDeps],
    exam_id: UUID,
    subject_code: str | None = None,
    limit: int = 50,
) -> ExamScoresResult:
    """获取考试成绩概览和学生得分列表。"""
    meta = GET_EXAM_SCORES_META

    # 1. 安全硬检查
    call = await ctx.deps.policy.before_tool(meta, {
        "exam_id": str(exam_id),
        "subject_code": subject_code,
    })

    # 2. 独立 session + DataScope 强制过滤
    async with ctx.deps.db_sessionmaker() as db:
        rows = await load_exam_scores_scoped(
            db,
            school_id=ctx.deps.data_scope.school_id,
            exam_id=exam_id,
            visible_class_ids=ctx.deps.data_scope.class_ids,
            subject_code=subject_code,
            limit=limit,
        )

    # 3. Artifact 化 + 脱敏
    observation = await ctx.deps.artifacts.process(
        meta=meta,
        rows=rows,
        summary_fn=summarize_exam_scores,
    )

    # 4. 审计 + 预算扣减
    await ctx.deps.policy.after_tool(call, observation)

    return observation
```

**核心变化：**
- 参数从 `dict` 变成显式类型（Pydantic 自动生成 tool schema）
- `ToolContext` 变成 `RunContext[AgentDeps]`
- 数据库从共享 `ctx.db` 变成独立 `ctx.deps.db_sessionmaker()`
- 安全检查从"可选"变成"第一行必须调用"
- 结果从裸 dict 变成经 ArtifactManager 处理的脱敏输出

### 6.3 RBAC 动态过滤

每次 run 只注册当前用户允许的工具：

```python
allowed_tools = tool_catalog.allowed_for(
    role=deps.role,
    modules=deps.enabled_modules,
    capabilities=deps.capabilities,
    data_scope=deps.data_scope,
)

agent = Agent(
    model=model,
    deps_type=AgentDeps,
    tools=[t.fn for t in allowed_tools],
    system_prompt=prompt,
)
```

工具内部 `before_tool()` 仍然做二次硬检查（防止注册逻辑 bug 导致越权）。

### 6.4 写工具的 Deferred 模式

```python
ADJUST_SCORES_META = EduToolMeta(
    name="adjust_scores",
    ...,
    is_read_only=False,
    risk_level="high",
)

@agent.tool(name="adjust_scores")
async def adjust_scores(
    ctx: RunContext[AgentDeps],
    exam_id: UUID,
    adjustment: float,
    reason: str,
) -> AdjustResult:
    """批量调整成绩（需要教师确认）。"""
    meta = ADJUST_SCORES_META
    call = await ctx.deps.policy.before_tool(meta, {...})

    # deferred tools 机制：暂停等确认
    confirmation = await ctx.deps.confirmations.request(
        run_id=ctx.deps.run_id,
        tool_name=meta.name,
        summary=f"将为 {count} 名学生调整成绩 {adjustment:+.1f} 分",
        impact={"students": count, "exam_id": str(exam_id)},
        risk_level=meta.risk_level,
    )

    if not confirmation.approved:
        return AdjustResult(success=False, message="教师已拒绝此操作")

    # 执行写操作
    async with ctx.deps.db_sessionmaker() as db:
        result = await do_adjust_scores(db, ...)

    await ctx.deps.policy.after_tool(call, result)
    return result
```

---

## 7. 实施计划

### 第 1 步：Spike 验证（1-2 天）

**目标：** 验证 Pydantic AI 能否和 llm-proxy 完整跑通。

**产出：**
- 一个独立脚本，不经过旧 runtime/registry/loop
- 验证：llm-proxy slot header、streaming、一个读工具、一个 deferred 写工具、typed output

**验收：** Agent 能通过 llm-proxy 调用模型，执行工具，流式返回结果。

**风险门控：** 如果 Pydantic AI 和 llm-proxy 不兼容（deferred tools 行为异常、streaming 格式不匹配），在此步终止评估。

### 第 2 步：核心安全层（4-5 天）

**目标：** 建立 edu-cloud 特色层的骨架。

**产出：**
- `AgentDeps` dataclass
- `EduToolMeta` dataclass
- `PolicyToolGuardrail`（before_tool / after_tool）
- `AgentBudget`（请求级）
- `ConfirmationBroker`（内存版）
- `TraceRecorder`（JSONL 版）
- `ArtifactManager`（DB 版）
- 数据库 migration（ai_artifacts / ai_agent_trace / ai_agent_trace_event / ai_confirmations）

**验收：** 越权工具调用被 PolicyToolGuardrail deny，即使直接调用也 fail-closed。

### 第 3 步：Runtime/API 重写（4-5 天）

**目标：** EduAgentRuntime 替代旧 runtime，主路径不 import 旧组件。

**产出：**
- `EduAgentRuntime`（构建 AgentDeps → Pydantic Agent → SSE 翻译）
- `POST /api/v1/ai/chat` 重写
- `POST /api/v1/ai/runs/{run_id}/confirmations/{id}` 新增
- SSE 事件兼容（thinking/tool_call/tool_result/answer/done + confirmation_required/resolved/timeout）

**验收：** 前端 AiSlidePanel 不因 SSE 格式变化崩溃。主路径 `rg "AgentLoop|Supervisor|ToolRegistry|LLMProxyAdapter"` 零命中。

### 第 4 步：63 个工具原生重写（12-18 天）

**目标：** 全部工具迁移到 `@agent.tool` 原生模式。

**按 domain 分批：**

| 批次 | Domain | 工具数 | 预估 |
|------|--------|--------|------|
| 4a | exam + students（基础查询） | 11 | 2-3d |
| 4b | analytics（统计分析） | 14 | 3-4d |
| 4c | knowledge（知识库） | 7 | 1-2d |
| 4d | homework + grading（作业阅卷） | 8 | 2-3d |
| 4e | conduct（德育） | 8 | 2-3d |
| 4f | profile + bank + adaptive（画像题库） | 9 | 2-3d |
| 4g | card + actions + agent 内部 | 6 | 1-2d |

**每批验收：**
- 每个工具有 `EduToolMeta`
- 每个工具第一行调 `before_tool()`
- 查询走 DataScope scoped helper
- 结果走 ArtifactManager
- policy 测试（越权/跨班/跨校 deny）
- PII 测试（学生姓名不出现在返回值）

### 第 5 步：写确认 + 前端（4-6 天）

**目标：** 完整的写操作确认闭环。

**产出：**
- ConfirmationBroker DB 版（持久化 pending）
- 前端确认卡片 UI（AiSlidePanel 内）
- approve/reject/timeout 全路径
- 幂等性保证

**验收：** 未确认前 DB 无写入。超时后返回"未执行"。重复提交幂等。

### 第 6 步：Artifact / Memory / Context（4-5 天）

**目标：** 大结果不爆上下文，跨会话可续接。

**产出：**
- 大结果自动 artifact 化
- `query_artifact` / `filter_artifact` 工具（按 artifact_id 查询明细）
- 跨会话 artifact 摘要加载
- 上下文压缩策略

**验收：** 500 学生成绩分析不爆上下文，trace 不含学生明细 PII。

### 第 7 步：Trace / Audit / Output 校验（3-4 天）

**目标：** 完整的可观测性和输出质量保证。

**产出：**
- TraceRecorder DB 版
- 审计关联（trace ↔ tool_call ↔ confirmation）
- Pydantic output model（TeacherAnswer）
- 数值校验（成绩范围、人数一致性）

**验收：** 教师可见过程清晰，审计可回放，敏感值不落 trace。

### 第 8 步：删除旧引擎 + 回归验证（2-3 天）

**目标：** 清理旧代码，确认无回归。

**产出：**
- 旧组件移入 `_deprecated/` 或删除
- 全量回归测试
- 文档更新

**验收：** `rg "ToolRegistry|AgentLoop|LLMProxyAdapter"` 在生产路径零命中。所有工具 + SSE + 确认 + 预算 + trace 全链路通过。

### 总计：34-48 工作日

---

## 8. 风险矩阵

| 风险 | 影响 | 概率 | 缓解 |
|------|------|------|------|
| Pydantic AI deferred tools 与 llm-proxy 不兼容 | 严重 | 低 | Spike（第 1 步）门控 |
| llm-proxy X-LLM-Slot header 丢失 | 严重 | 低 | 自定义 AsyncOpenAI client 注入 header |
| 工具重写安全回归 | 严重 | 中 | 静态检查要求 before_tool() + 越权/跨校测试 |
| PII 泄漏到模型/SSE/trace | 严重 | 中 | ArtifactManager 统一脱敏 + PII denylist 测试 |
| DB session 并行问题 | 中 | 低 | P0 串行（独立 session），P1 评估只读并行 |
| Pydantic AI 版本快速迭代 | 中 | 中 | 锁定 v1.93.x，不追最新 |
| 63 工具重写周期长 | 中 | 高 | 按 domain 分批，每批独立验收 |
| 大爆炸上线风险 | 中 | 中 | 部署保留上一版可回滚，数据库 migration 向后兼容 |

---

## 9. 验收清单

### P0 完成标准

- [ ] Spike 通过：Pydantic AI + llm-proxy + streaming + deferred tools 全跑通
- [ ] AgentDeps 替代 ToolContext，所有工具用 RunContext[AgentDeps]
- [ ] 63 个工具全部有 EduToolMeta + before_tool() 硬检查
- [ ] 写操作无确认 token 时 PolicyToolGuardrail deny
- [ ] AgentBudget 在 token/tool/write/wall_clock 任一超限时停止
- [ ] SSE confirmation_required 事件 → 前端确认卡 → POST 回传
- [ ] 超时 5 分钟后返回"操作未执行"
- [ ] 大结果自动 artifact 化，模型/SSE 不泄漏 raw 学生数据
- [ ] Trace 记录全部决策事件，不含 PII
- [ ] 旧 AgentLoop/ToolRegistry/LLMProxyAdapter 不在生产路径
- [ ] 前端 AiSlidePanel 不因 SSE 格式变化崩溃
- [ ] 教师体验：一个通用 agent，自然对话，自主调工具，写操作有确认

---

## 附录 A：框架选型调研结论

| 框架 | 结论 | 理由 |
|------|------|------|
| **Pydantic AI** | **采用** | RunContext 与 ToolContext 同构，FastAPI 生态，多模型，类型安全 |
| LangGraph | 点状借鉴 | interrupt/checkpoint 模式参考，但 edu-cloud 已有等价自建 |
| OpenAI Agents SDK | 参考 tracing 设计 | Guardrails + Tracing 好，但锁定 OpenAI API |
| CrewAI | 不采用 | multi-agent 为核心，单 agent 是负担 |
| AutoGen | 不采用 | 已进入 maintenance mode |
| Dify | 不采用 | 全栈平台无法嵌入 |
| FastGPT | 不采用 | 开源版无多租户 |
| Claude Agent SDK | 不采用 | 面向文件系统操作，非业务工具 |

## 附录 B：Claude + GPT 共识

1. Pydantic AI 是引擎，不是安全边界；安全层必须 edu-cloud 自建
2. 不做 wrapper / bridge / 双引擎，一步到位原生重写
3. 通用智能体，不做场景路由
4. 每个工具第一行 before_tool()，不信任注册期过滤是唯一防线
5. DB session 每工具独立，不共享
6. 确认超时 5 分钟（教师被课堂打断是常态）
7. Artifact 阈值 32KB / 50 行
8. Trace 不记 chain-of-thought，记结构化决策事实
9. Spike 是第一步门控，不通过则终止
10. 锁定 Pydantic AI v1.93.x，不追最新
