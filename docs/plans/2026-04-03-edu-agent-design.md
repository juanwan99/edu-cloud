# edu-agent — 教育域智能 Agent 内核设计

> 基于 Claude Code 架构裁剪，嵌入 edu-cloud，驱动教师助手和家长顾问两个场景。
> 设计时间：2026-04-03 15:46
> [2026-04-04 10:32:00 实现完成] 架构级偏差 2 项已对齐 | 偏差来源: Integration Review GPT 发现 | Commits: ae568cb..e1a28f7
> - F001: config.LLM_API_URL 语义：原决策"完整 endpoint URL" → 新决策"基地址（不含路径）"，LLMProxyAdapter 内部追加 /v1/chat/completions — 原因: 双重拼接导致请求地址错误
> - F002: Session 隔离：原设计无 owner 概念 → 新增 _SessionState.owner_id + list/delete 按 owner 过滤 + 403 越权拒绝 — 原因: 多用户环境下任意用户可操作他人会话

## §0 设计决策记录

| # | 决策 | 结论 | 理由 |
|---|------|------|------|
| D1 | 部署形态 | 嵌入 edu-cloud，替换现有 `ai/` 模块 | Agent 工具需要直接访问 ORM 层（ScopeFilter、权限过滤），走 API 绕一圈会丢失上下文 |
| D2 | LLM 调用 | 通过 llm-proxy 统一调用，不绑死任何模型 | 学校用不起 Claude API + 政策风险，必须支持国产模型 |
| D3 | 双通道 | 主通道（国产模型，学校自有 key）+ 增强通道（中转服务，脱敏后路由） | 主通道低成本合规（¥350/月），增强通道按量付费高智能 |
| D4 | 能力分级 | Tier 1/2/3 按模型能力自动降级循环策略 | 弱模型硬跑复杂循环会胡说八道，必须适配 |
| D5 | 改造范围 | 激进替换，直接重写，保证测试全绿 | 开发阶段无线上用户，无回归风险 |
| D6 | 工具接口 | 标准化重构为 `tool.call(input, context) → ToolResult` | 质量第一，可维护性优先，接受早期复杂度 |
| D7 | 技术栈 | Python（与 edu-cloud 同栈） | Agent 循环是 IO 密集型（95% 时间等 LLM 响应），Python asyncio 足够 |
| D8 | 部署架构 | 云端 SaaS（你的服务器） | 行业主流（七天网络、科大讯飞均为云端），学校免费+家长付费模式验证 |
| D9 | claw-code 角色 | 参考手册（架构模式+行为规范），不直接使用代码 | Python parity 版是移植骨架，核心模块为空；价值在 reference_data + PARITY.md |

## §1 项目定位

### 一句话

基于 Claude Code 架构裁剪的教育域智能 Agent——能规划、能自省、能记忆，驱动 edu-cloud 的教师助手和家长顾问。

### 对标

| 能力 | Claude Code | edu-agent |
|------|------------|-----------|
| 多步规划 | ✓ TaskCreateTool | ✓ TaskPlanner |
| 并行工具 | ✓ toolOrchestration | ✓ ToolOrchestrator |
| 自省纠错 | ✓ 验证循环 | ✓ Tier 1 verify |
| 上下文压缩 | ✓ 4 层 | ✓ 2 层（够用） |
| 会话记忆 | ✓ SessionMemory | ✓ SessionMemoryExtractor |
| 子代理 | ✓ AgentTool | ✓ Tier 1（预留） |
| 代码编写 | ✓ Read/Write/Edit/Bash | ✗ 有意砍掉 |
| 文件/Git | ✓ | ✗ 有意砍掉 |
| CLI/TUI | ✓ | ✗ Web only |
| 双通道路由 | ✗ | ✓ 教育域特有 |
| 能力探测降级 | ✗ | ✓ 多模型适配 |
| 敏感度分类 | ✗ | ✓ 学生数据保护 |

### 不做什么

- 不做 CLI/TUI
- 不做代码编辑工具（Read/Write/Edit/Bash/Git 全砍）
- 不做 IDE 集成
- 不做 MCP server（预留接口，不实现）
- 不做 Skill/Plugin 加载系统（预留接口，不实现）

## §2 架构全景

```
┌─────────────────────────────────────────────────────────────┐
│                      edu-cloud (FastAPI)                     │
│                                                             │
│  ┌─────────────────── edu-agent 内核 ───────────────────┐   │
│  │                                                      │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │   │
│  │  │ Agent    │  │ Tool     │  │ Context          │   │   │
│  │  │ Loop     │→ │ Executor │  │ Manager          │   │   │
│  │  │          │  │          │  │ (压缩+记忆)       │   │   │
│  │  └────┬─────┘  └────┬─────┘  └──────────────────┘   │   │
│  │       │              │                               │   │
│  │  ┌────┴─────┐  ┌────┴──────────────────────────┐    │   │
│  │  │ Task     │  │ Tool Registry                  │    │   │
│  │  │ Planner  │  │ ┌────────┐┌────────┐┌────────┐│    │   │
│  │  │ (规划器)  │  │ │教务工具 ││家长工具 ││未来... ││    │   │
│  │  └──────────┘  │ │ 39个   ││ N个    ││PPT/论文││    │   │
│  │                │ └────────┘└────────┘└────────┘│    │   │
│  │  ┌──────────┐  └──────────────────────────────┘     │   │
│  │  │ LLM      │                                       │   │
│  │  │ Adapter  │← 统一接口，适配所有 LLM provider       │   │
│  │  └────┬─────┘                                       │   │
│  └───────┼─────────────────────────────────────────────┘   │
│          │                                                  │
│          ▼                                                  │
│  ┌──────────────┐                                          │
│  │  llm-proxy   │→ DeepSeek / Qwen / Claude / GPT          │
│  │  (port 8100) │                                          │
│  └──────────────┘                                          │
└─────────────────────────────────────────────────────────────┘
```

### 核心模块

| 模块 | 职责 | 来源 |
|------|------|------|
| **AgentLoop** | 主循环：接收目标→规划→执行→验证→响应 | 借鉴 Claude Code `query.ts` |
| **TaskPlanner** | 复杂目标拆解为子任务链，管理依赖 | 借鉴 `TaskCreateTool` |
| **ToolExecutor** | 工具执行管道：权限→校验→执行→错误处理 | 借鉴 `toolExecution.ts` |
| **ToolOrchestrator** | 并发/串行分批，只读并发写操作串行 | 借鉴 `toolOrchestration.ts` |
| **ContextManager** | 上下文压缩 + token 计算 | 借鉴 `compact/` |
| **SessionMemoryExtractor** | 会话记忆提取 + 持久化 | 借鉴 `SessionMemory/` |
| **LLMAdapter** | 统一 LLM 调用接口，适配多 provider | 改造现有 `llm.py` |
| **CapabilityProbe** | 检测模型能力，决定循环策略 tier | 新建 |
| **SensitivityRouter** | 请求敏感度分类，路由到主/增强通道 | 新建 |
| **ToolContext** | 标准化工具上下文 | 重构现有 |
| **ToolRegistry** | 工具注册、发现、权限过滤 | 重构现有 |

## §3 Agent Loop（主循环）

### 流程

```
用户输入 (goal)
    │
    ▼
AgentLoop.run(goal, context)
  ① CapabilityProbe → 确定 Tier (1/2/3)
  ② SensitivityRouter → 确定通道 (主/增强)
  ③ 构建 system prompt
  ④ while not done:
     ├─ LLM 采样
     ├─ 返回 answer → yield AgentEvent.answer → done
     ├─ 返回 tool_calls → ToolOrchestrator 分批执行 → 结果注入 → continue
     └─ 返回 plan → TaskPlanner 拆解 → 逐任务执行
  ⑤ 状态检查 (Transitions):
     ├─ turn > max → 强制结束
     ├─ token > threshold → 压缩
     ├─ errors > 3 → 降级或终止
     └─ 正常 → next_turn
  ⑥ ContextManager.extract_memory (后台)
  ⑦ yield AgentEvent.done
```

### 三个 Tier 的循环差异

| 能力 | Tier 1 (Claude/GPT) | Tier 2 (DeepSeek/Qwen) | Tier 3 (轻量/本地) |
|------|---------------------|----------------------|------------------|
| max_turns | 25 | 15 | 8 |
| parallel_tools | ✓ | ✓ | ✗ |
| task_planning | ✓ | ✓ | ✗ |
| self_verify | ✓ | ✗ | ✗ |
| sub_agents | ✓ | ✗ | ✗ |
| context_compact | ✓ | ✓ | ✗ |
| memory_extract | ✓ | ✗ | ✗ |

### 状态对象

```python
@dataclass
class AgentState:
    messages: list[Message]
    turn_count: int = 0
    token_count: int = 0
    tasks: list[Task] | None = None
    current_task_id: str | None = None
    error_count: int = 0
    transition: Transition | None = None
    channel: str = "primary"  # primary | enhanced | primary_locked
```

### Transition 枚举

```python
class Transition(Enum):
    NEXT_TURN = "next_turn"
    COMPACT = "compact"
    ERROR_RETRY = "error_retry"
    TIER_DOWNGRADE = "tier_downgrade"
    MAX_TURNS = "max_turns"
    BUDGET_EXHAUSTED = "budget_exhausted"
    DONE = "done"
```

### AgentEvent 流式输出

```python
@dataclass
class AgentEvent:
    type: str   # "thinking" | "plan" | "task_update" | "tool_call" | "tool_result" | "answer" | "error" | "done"
    data: dict
```

前端 SSE 示例：
```
{"type": "thinking",    "data": {"content": "我需要先收集各班成绩..."}}
{"type": "plan",        "data": {"tasks": [...]}}
{"type": "task_update", "data": {"id": "1", "status": "in_progress"}}
{"type": "tool_call",   "data": {"tool": "get_class_stats", "args": {...}}}
{"type": "tool_result", "data": {"tool": "get_class_stats", "result": {...}}}
{"type": "answer",      "data": {"content": "三年级期中考试分析如下..."}}
{"type": "done",        "data": {"turns": 5, "tokens": 12000}}
```

## §4 工具体系

### 标准化接口

```python
@dataclass
class ToolContext:
    db: AsyncSession
    school_id: str
    user_id: str
    role: str
    class_ids: list[str] | None
    subject_codes: list[str] | None
    grade_ids: list[str] | None
    capabilities: dict
    enabled_modules: list[str]
    anonymizer: Anonymizer | None

@dataclass
class ToolResult:
    success: bool
    data: dict | list | str | None
    error: str | None = None
    metadata: dict | None = None
    is_read_only: bool = True
```

### ToolSpec 定义

```python
class ToolSpec:
    name: str
    description: str
    parameters: dict              # JSON Schema
    func: Callable[[dict, ToolContext], Awaitable[ToolResult]]
    category: str
    domain: str
    risk_level: str               # "low" | "medium" | "high"
    is_read_only: bool            # 决定能否并发执行
    allowed_roles: list[str] | None
    requires_capabilities: list[tuple[str, str]]
    sensitivity: str              # "public" | "school" | "student"
```

### 工具注册示例

```python
@registry.register(
    name="get_exam_summary",
    description="获取考试各科汇总统计",
    parameters={"exam_id": {"type": "string"}, "subject_id": {"type": "string", "optional": True}},
    domain="analytics",
    is_read_only=True,
    sensitivity="school",
    allowed_roles=["academic_director", "grade_leader", "principal"],
    requires_capabilities=[("analytics", "read")],
)
async def get_exam_summary(input: dict, ctx: ToolContext) -> ToolResult:
    exam_id = input["exam_id"]
    # ... 业务逻辑 ...
    return ToolResult(success=True, data={...})
```

### 并发分批策略

借鉴 Claude Code `toolOrchestration.ts`：
- 连续的 `is_read_only=True` 工具 → 同一批，`asyncio.gather` 并发（上限 10）
- `is_read_only=False` 工具 → 单独一批，串行执行

### 权限三层过滤

与现有设计一致，输入输出标准化：
- Layer 1: RBAC（allowed_roles）
- Layer 2: Module 开关（module_code in enabled_modules）
- Layer 3: Capability 矩阵（requires_capabilities）

### sensitivity 字段（新增）

| 值 | 含义 | 通道影响 |
|---|------|---------|
| `public` | 不含学校/学生信息 | 可走增强通道 |
| `school` | 含学校级数据 | 主通道 |
| `student` | 含学生级数据 | 主通道，且锁定本会话 |

### 39 个现有工具迁移

每个工具改动 ~15 行（签名 + return 包装），业务逻辑不变。总计 ~585 行机械重构。

### 家长端工具（后续批次，不在本次实现范围）

```
get_my_child_overview      # 学情概览
get_my_child_trend         # 成绩趋势
get_my_child_weakness      # 薄弱知识点
get_recommended_exercises  # AI 推荐练习
get_learning_plan          # 个性化学习计划
get_error_book_summary     # 错题本摘要
```

架构支持验证：注册时 `allowed_roles=["parent"]` 即可，内核零改动。

## §5 LLM Adapter + 双通道路由

### LLM 统一接口

```python
class LLMAdapter(Protocol):
    async def chat(self, request: LLMRequest) -> LLMResponse: ...
    async def chat_stream(self, request: LLMRequest) -> AsyncGenerator[LLMChunk, None]: ...
    def supports_tool_use(self) -> bool: ...
    def supports_parallel_tool_calls(self) -> bool: ...
    def context_window_size(self) -> int: ...
```

### LLMProxyAdapter

通过 llm-proxy (port 8100) 调用，slot 机制选 provider。发送 OpenAI 格式请求，llm-proxy 内部适配各 provider 差异。

### CapabilityProbe

启动时用一个简单的 tool_call 测试探测模型能力，结果缓存。管理员也可手动指定 Tier 覆盖。

```
tool_use + parallel_tools + context_window >= 100k → Tier 1
tool_use + context_window >= 30k                   → Tier 2
其他                                                → Tier 3
```

### SensitivityRouter

```python
class SensitivityRouter:
    def route(self, state: AgentState, tool_specs: list[ToolSpec]) -> LLMProxyAdapter:
        # 无增强通道 → 主通道
        # 已调用过 student 工具 → 锁定主通道
        # 可用工具全是 public → 增强通道
        # 否则 → 主通道

    def on_tool_executed(self, state: AgentState, spec: ToolSpec):
        # student 工具执行后锁定 channel = "primary_locked"
```

**安全原则：一旦碰过学生数据，本次会话不再切到增强通道。**

## §6 Context Manager

### 两层压缩

| 层 | 触发 | 做法 |
|---|------|------|
| Auto Compact | token > context_window × 70% | LLM 对早期消息做摘要，保留最近 4 轮 |
| Memory Extract | 会话结束 | 后台提取关键发现，写入 AgentMemory 表 |

### 压缩摘要 prompt

让 LLM 按优先级保留：
1. 已确认的数据发现（具体数字和结论）
2. 用户的原始需求和约束
3. 已完成/未完成的任务
4. 发现的异常和待验证假设

丢弃：工具调用原始 JSON、重复中间步骤、已纠正的错误结论。

### Token 计算

粗估（不依赖特定 tokenizer）：中文 1 字 ≈ 1.5 token，英文 1 word ≈ 1.3 token。配合 13k buffer 足够安全。

### AgentMemory 持久化

```python
class AgentMemory(Base):
    school_id: str
    session_id: str
    user_id: str
    memory_type: str       # "finding" | "preference" | "follow_up"
    content: str
    entity_type: str | None  # "student" | "class" | "school"
    entity_id: str | None
    expires_at: datetime | None
    is_active: bool = True
```

新会话自动加载相关记忆（school_id + user_id + is_active + 未过期），最近 20 条注入 system prompt。

## §7 TaskPlanner

### 触发逻辑

不用分类器。LLM 自己决定——system prompt 里告诉它"如果任务需要多步，先输出计划"。返回 plan 格式走规划路径，返回 tool_call 走直接执行。

### 数据结构

```python
@dataclass
class Task:
    id: str
    description: str
    status: str = "pending"            # pending | in_progress | completed | failed
    tools_hint: list[str] | None = None
    depends_on: list[str] | None = None
    result_summary: str | None = None
    verify: str | None = None          # 验证条件（Tier 1 only）

@dataclass
class Plan:
    goal: str
    tasks: list[Task]
    current_task_index: int = 0
```

### 执行流程

1. `maybe_plan(goal)` → LLM 判断是否需要规划
2. 有 Plan → 按依赖拓扑排序，逐任务执行
3. 每个 Task 作为子目标跑 ReAct 循环
4. Tier 1: 每个 Task 完成后跑验证步骤
5. 全部完成 → 综合总结

### 自省验证（Tier 1 only）

Task 完成后，让 LLM 检查：
- 结论是否有数据支撑？
- 是否存在偏差（缺考、样本量、题目难度）？
- 是否需要额外数据交叉验证？

如果发现问题，给它工具让它主动验证。

## §8 文件结构

```
src/edu_cloud/ai/
├── agent_loop.py           # 主循环 (~300 行)
├── task_planner.py         # 规划器 (~200 行)
├── tool_executor.py        # 执行管道 + 并发分批 (~200 行)
├── context_manager.py      # 压缩 + token 计算 (~150 行)
├── session_memory.py       # 记忆提取 (~100 行)
├── llm_adapter.py          # LLM Adapter (~200 行)
├── capability_probe.py     # 能力探测 (~80 行)
├── sensitivity_router.py   # 双通道路由 (~80 行)
├── tool_context.py         # ToolContext, ToolResult (~60 行)
├── registry.py             # ToolRegistry 重构 (~100 行)
├── tool_access.py          # 三层权限过滤 (~60 行)
├── prompts.py              # system prompt 模板 (~100 行)
├── anonymizer.py           # 保留不动
├── schemas.py              # 扩展 AgentEvent
├── tools/
│   ├── exams.py            # 3 工具
│   ├── analytics.py        # 5 工具
│   ├── analytics_compare.py # 3 工具
│   ├── analytics_score.py  # 2 工具
│   ├── students.py         # 4 工具
│   ├── knowledge.py        # 4 工具
│   ├── knowledge_db.py     # 2 工具
│   ├── homework.py         # 5 工具
│   ├── grading_ops.py      # 3 工具
│   ├── bank.py             # 2 工具
│   ├── profile.py          # 4 工具
│   └── actions.py          # 2 工具
```

新增 model：`models/agent_memory.py`
API 改动：`api/ai.py` 适配新 AgentEvent + 记忆管理端点

### 废弃文件

| 删除 | 替换为 |
|------|--------|
| ai/agent.py | agent_loop.py |
| ai/llm.py | llm_adapter.py |
| ai/llm_factory.py | sensitivity_router.py |
| ai/model_router.py | capability_probe.py |
| ai/intent_resolver.py | 合并入 sensitivity_router.py |
| ai/context.py | context_manager.py + prompts.py |

### 模块依赖（单向无环）

```
agent_loop
    ├──→ task_planner
    ├──→ tool_executor ──→ registry ──→ tool_context
    │                  ──→ tool_access
    ├──→ context_manager
    ├──→ session_memory
    ├──→ sensitivity_router ──→ llm_adapter
    ├──→ capability_probe ──→ llm_adapter
    └──→ prompts

tools/* ──→ tool_context（唯一依赖）
```

### 代码量

核心引擎 ~1,660 行 + 工具改造 ~585 行 = **~2,245 行**

## §9 部署架构

### 商业模式

```
B2B（学校免费）: edu-cloud 考试管理 + AI 阅卷 + 教师 Agent
B2C（家长付费）: 学情画像 + 个性化推荐 + AI 学习规划
```

参考七天网络模式（2 万+ 学校，1500 万+ 家长，近 2 亿融资）。

### 部署拓扑

```
你的云服务器（SaaS）
├── edu-cloud 全量部署
│   ├── 教师端（免费）
│   ├── 家长端（付费）
│   ├── Agent 内核
│   └── 学生数据库
├── llm-proxy
│   ├── 主 slot → DeepSeek / Qwen（学校配置）
│   └── 增强 slot → Claude / GPT（你的中转）
└── 合规措施
    ├── 家长注册授权同意
    ├── 教育 APP 备案
    ├── 不发布排名（2018 教育部禁令）
    └── 数据安全等保
```

### 费用估算（200 教师学校）

| 通道 | 模型 | 月费 |
|------|------|------|
| 主通道 | DeepSeek-V3 | ~¥350 |
| 增强通道 | Claude Sonnet（按量） | ~¥100-200 |

## §10 扩展预留

### 已确认的未来扩展

| 扩展 | 架构支持方式 | 内核改动 |
|------|------------|---------|
| 家长端工具 | 注册新工具 + `allowed_roles=["parent"]` | 零 |
| 论文写作 | 注册论文域工具，调 paper-skill API | 零 |
| PPT 制作 | 注册 `ppt_render_slide` 沙箱工具，Agent 生成 HTML/CSS 作为工具参数 | 零 |
| 巡检 Agent | 定时任务触发 AgentLoop.run()，工具集限定为分析类 | 零 |
| 本地部署 | Docker Compose 打包，llm-proxy slot 指向本地模型 | 零 |
| MCP 集成 | LLMAdapter 扩展 MCP client | 预留接口 |

### 沙箱代码工具模式（PPT/论文数据分析）

Agent 把代码当作工具参数传入，工具内部沙箱执行。Agent 内核不感知"代码"的存在。

```python
@registry.register(name="ppt_render_slide", risk_level="high")
async def ppt_render_slide(input: dict, ctx: ToolContext) -> ToolResult:
    html = input["html"]       # Agent 生成的 HTML
    css = input["css"]         # Agent 生成的 CSS
    # 白名单校验 → 数据绑定 → iframe sandbox 渲染
```

## §11 参考来源

| 来源 | 用途 |
|------|------|
| `claude-code-sourcemap/` | 架构模式：query.ts, toolOrchestration.ts, runAgent.ts, compact/, SessionMemory/ |
| `claw-code/reference_data/` | 工具定义原件（JSON Schema） |
| `claw-code/PARITY.md` | Claude Code 行为规范清单（edge case、安全检查） |
| `claw-code/rust/crates/` | Rust 实现参考（工具执行、权限、沙箱） |
| 七天网络商业模式 | B2B 免费 + B2C 家长付费，已验证 |
| 科大讯飞智学网 | 云端 SaaS + 区域私有云混合部署参考 |
