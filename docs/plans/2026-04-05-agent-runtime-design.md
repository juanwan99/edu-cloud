# Agent Runtime 架构升级设计

> 创建: 2026-04-05 22:53:35
> [2026-04-06 11:10:00 实现完成] Commits: 511e939..09fdd75
> 依赖: Phase 1 多 Agent 编排（已完成）、Phase 2 跨会话记忆（已完成）

## §待处置

- **F006 (test-gap MED)**: ai.py finally 块的 history 回写和 run_info 透传缺少执行型 API 集成测试（当前用源码文本检查替代）。GPT 3 轮审查后仍要求完整 HTTP mock + SSE 消费 + finally 执行的集成测试。下个 Phase 补充。
- **F003 (accepted-risk)**: HTTP 入口 user_slots/system_slots 硬编码空，dual-model DB 接线待独立设计任务。

## §0 目标

将 edu-cloud Agent 从"HTTP 请求附属品"升级为"可被多种方式调用的独立运行时"。三个核心能力：

1. **多入口** — HTTP API / arq Worker / CLI 共用同一个 AgentRuntime
2. **双层模型** — 用户自备主力模型 + 可选付费增强模型，路由零 token 消耗
3. **防幻觉** — Grounded Generation 三层防线，数据类回复必须有来源可追溯

设计原则：**主力模型能独立运行全部功能，增强模型是锦上添花。**

## §1 AgentRuntime（核心调度器）

统一入口，接收任务请求，编排模型选择→执行→后处理。替代现在分散在 `api/ai.py` 里的编排逻辑。

```python
class AgentRuntime:
    """Agent 统一运行时，与传输层无关。"""
    
    async def run(
        self,
        message: str,
        context: AgentContext,
    ) -> AsyncGenerator[AgentEvent, None]:
        # 1. ModelRouter 选模型
        model_choice = await self._model_router.route(message, context)
        adapter = self._create_adapter(model_choice)
        
        # 2. MemoryInjector 加载记忆
        memory_context = ""
        if model_choice.tier != "minimal":
            memory_context = await self._memory_injector.build_context(
                db=context.db, school_id=context.school_id,
                user_id=context.user_id, role=context.role,
                class_ids=context.data_scope.visible_class_ids,
                student_ids=context.data_scope.visible_student_ids,
            )
        
        # 3. CapabilityProbe → LoopStrategy
        strategy = await self._probe.detect(adapter)
        
        # 4. Supervisor.handle() 执行
        supervisor = Supervisor(
            registry=self._registry,
            adapter=adapter,
            strategy=strategy,
            team_registry=self._team_registry,
            sensitivity_router=self._sensitivity_router,
            memory_extractor=self._memory_extractor if strategy.tier == 1 else None,
        )
        
        system_prompt = build_teacher_prompt(context.role, context.school_id) + memory_context
        
        collected_tool_results = []
        async for event in supervisor.handle(
            message=message, ctx=context.tool_ctx,
            tool_specs=self._resolve_tools(context),
            system_prompt=system_prompt,
            session_id=context.session_id,
        ):
            # 5. 收集工具结果用于输出校验
            if event.type == "tool_result":
                collected_tool_results.append(event.data)
            
            # 6. answer 事件经 OutputValidator 校验
            if event.type == "answer":
                validated = await self._validator.validate(
                    event.data.get("content", ""), collected_tool_results
                )
                if validated.status == "fail":
                    # 用工具原始数据重新生成
                    event = await self._regenerate_grounded(event, collected_tool_results, adapter)
                elif validated.status == "warn":
                    event = self._annotate_unverified(event, validated.ungrounded_values)
            
            yield event
```

### AgentContext

封装一次请求的所有上下文：

```python
@dataclass(frozen=True)
class AgentContext:
    db: AsyncSession
    user_id: str
    school_id: str
    role: str
    data_scope: DataScope
    session_id: str
    tool_ctx: ToolContext          # 现有，传给 Supervisor
    # 模型配置
    user_slots: list[LLMSlot]     # 用户自备
    system_slots: list[LLMSlot]   # 系统增强（可能为空）
    enhanced_enabled: bool         # 是否开通增强版
```

### 三个入口构造 AgentContext 的方式

| 入口 | 构造方式 |
|------|---------|
| HTTP API | JWT 解析 user/role/school → DB 查 slots + DataScope |
| arq Worker | 任务参数 school_id + task_type → DB 查 slots + 预定义 role |
| CLI | 命令行参数 → DB 查 slots + 指定 role |

### 关键约束

- AgentRuntime 不持有状态，每次 `run()` 独立
- Supervisor/AgentLoop/Tools 完全不改
- 现有 `api/ai.py` 瘦身为 ~40 行 HTTP 序列化胶水

## §2 ModelRouter（双层模型路由）

根据任务类型 + 用户配置选择模型，零 token 消耗。

### 路由逻辑

```
用户请求 → ModelRouter.route(message, context)
  ├── 增强未开通 → 主力模型（用户 slot）
  ├── 增强已开通 → 判断任务复杂度
  │     ├── 简单查询/对话 → 主力模型
  │     └── 复杂分析/长链推理 → 增强模型（系统 slot）
  └── 主力模型不可用 → 增强模型降级兜底（仅增强版用户）
```

### 复杂度判断（纯规则，不调 LLM）

```python
class ModelRouter:
    ENHANCE_TRIGGERS = {
        "tool_count": 3,       # 预估需要 ≥3 个工具 → 增强
        "workflow": True,       # 触发 workflow → 增强
        "analysis_keywords": ["分析", "报告", "对比", "趋势", "诊断"],
        "multi_step": True,     # 上下文含 TaskPlanner 输出 → 增强
    }
    
    async def route(self, message: str, context: AgentContext) -> ModelChoice:
        if not context.enhanced_enabled:
            return ModelChoice(slots=context.user_slots, tier="standard")
        
        if self._needs_enhancement(message, context):
            return ModelChoice(slots=context.system_slots, tier="advanced")
        
        return ModelChoice(slots=context.user_slots, tier="standard")
```

### 与现有路由的关系

- 现有 SensitivityRouter：决定"主通道 vs 学生通道"（安全路由）
- 新 ModelRouter：决定"主力 vs 增强"（能力路由）
- 两者正交：先 ModelRouter 选模型，再 SensitivityRouter 选通道

### 关键约束

- 主力模型必须能独立运行全部功能
- 路由判断零 token 消耗
- 前端可显示当前模型（"DeepSeek 回答" vs "深度分析模式"）
- 与现有 llm_slots 表兼容，不改表结构
- 增强模型失败时降级到主力

## §3 GroundedExecutor（防幻觉三层防线）

确保 Agent 输出的每个数据点有来源，每个推理有依据。

### 第一层：数据源标签（代码强制）

工具返回结果时自动打标签：

```python
# ToolResult 扩展
@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: str | None = None
    source: DataSource | None = None  # 新增

@dataclass
class DataSource:
    type: str          # "db_query" | "api_call" | "computed"
    table: str | None  # 源表
    ref: str | None    # 考试名/时间等可读引用
    queried_at: str    # ISO 时间戳
```

现有 42 个工具逐步添加 source 标签（机械工作，不阻塞主流程）。

### 第二层：Prompt 约束（LLM 侧辅助）

在 system prompt 注入硬规则：

```
【数据引用规则】
1. 涉及具体数值（分数、百分比、排名、人数）时，必须标注来源
2. 格式：数值（来源：XX考试/XX时间）
3. 禁止凭推测给出具体数值
4. 工具未返回的数据，说"暂无该数据"，不要编造
```

此层为辅助，不是主防线。

### 第三层：输出校验（后置守卫）

Agent 回复生成后、推送给用户前，轻量校验：

```python
class OutputValidator:
    """检查 Agent 回复中的数值是否与工具返回一致。"""
    
    async def validate(
        self, response: str, tool_results: list[ToolResult]
    ) -> ValidationResult:
        # 1. 正则提取 response 中的数值（xx分、xx%、xx人、xx名）
        # 2. 与 tool_results 中的实际数据比对
        # 3. 不匹配 → 标记为 ungrounded
        pass
```

### 处置策略

| 校验结果 | 处置 |
|---------|------|
| pass | 正常推送 |
| warn | 推送，数值旁标注"未验证" |
| fail | 拦截，用工具原始数据重新生成回复 |

### 关键约束

- OutputValidator 不调 LLM，纯正则 + 数值比对，零额外 token
- source 标签由工具代码添加，不由 LLM 添加（LLM 可伪造）
- fail 时重新生成（保证体验），不直接展示原始数据
- 校验只针对有工具调用的数据类回复，闲聊不触发

## §4 Worker 入口（定时/事件触发）

### 定时任务

复用 arq Worker：

```python
# worker.py 新增
async def run_agent_scheduled(ctx, school_id: str, task_type: str, params: dict):
    """定时 Agent 任务：用该校主力模型执行。"""
    async with async_session() as db:
        runtime = AgentRuntime(...)
        agent_ctx = await build_context_for_school(db, school_id, task_type)
        
        async for event in runtime.run(
            message=SCHEDULED_PROMPTS[task_type],
            context=agent_ctx,
        ):
            if event.type == "done":
                await persist_result(db, school_id, task_type, event.data)
```

预定义任务类型（本次不实现，只留接口）：

| task_type | 触发 | 模型 | 说明 |
|-----------|------|------|------|
| daily_grade_alert | 每日 7:00 | 主力 | 成绩异常预警 |
| weekly_class_report | 每周一 6:00 | 主力 | 班级周报 |
| exam_analysis | 事件触发 | 主力/增强 | 考试发布后自动分析 |

### 事件触发

复用 EventBus：

```python
@event_bus.on("exam.published")
async def on_exam_published(event_data: dict):
    school_id = event_data["school_id"]
    if not await is_module_enabled(db, school_id, "study_analytics"):
        return
    await arq_pool.enqueue_job(
        "run_agent_scheduled",
        school_id=school_id,
        task_type="exam_analysis",
        params={"exam_id": event_data["exam_id"]},
    )
```

### CLI 入口

单次执行，非交互式：

```bash
python -m edu_cloud.cli.agent --school YCSY2026 --role principal "三年级数学成绩分析"
# 输出 JSON lines
{"type": "tool_call", "data": {"name": "get_class_stats", ...}}
{"type": "answer", "data": {"content": "三年级数学平均 72.3 分..."}}
{"type": "done", "data": {}}
```

### 关键约束

- 定时任务用主力模型（消耗用户 token）
- 事件触发异步入队，不阻塞业务流程
- 学校级开关（现有 SchoolModule 控制）
- 结果写入 agent_findings 表

## §5 文件结构

### 新增文件

| 文件 | 行数估 | 职责 |
|------|--------|------|
| `src/edu_cloud/ai/runtime.py` | ~120 | AgentRuntime 统一调度器 |
| `src/edu_cloud/ai/model_router.py` | ~80 | 双层模型路由 |
| `src/edu_cloud/ai/grounded.py` | ~100 | OutputValidator 数值校验 + DataSource |
| `src/edu_cloud/cli/agent.py` | ~30 | CLI 入口 |
| `tests/test_ai/test_runtime.py` | ~120 | Runtime 三入口统一行为 |
| `tests/test_ai/test_model_router.py` | ~100 | 路由规则 + 降级 |
| `tests/test_ai/test_grounded.py` | ~120 | 数值提取 + 比对 + pass/warn/fail |
| `tests/test_ai/test_agent_cli.py` | ~60 | CLI 参数 + 输出格式 |

### 修改文件

| 文件 | 改动 | 说明 |
|------|------|------|
| `src/edu_cloud/api/ai.py` | 大幅瘦身 | 编排搬到 runtime.py，剩 ~40 行 HTTP 胶水 |
| `src/edu_cloud/ai/tool_context.py` | 小改 | ToolResult 加 source 字段 |
| `src/edu_cloud/ai/agent_loop.py` | 小改 | 输出前调 OutputValidator |
| `src/edu_cloud/ai/prompts.py` | 小改 | 加 Grounded 规则到模板 |
| `src/edu_cloud/worker.py` | 小改 | 注册 run_agent_scheduled |
| `src/edu_cloud/core/events.py` | 小改 | 加 exam.published → Agent 入队 |

### 不改的文件

- `supervisor.py` — 已解耦，AgentRuntime 直接调
- `memory_*.py` — Phase 2 完成，直接复用
- `tools/*.py`（42 个工具）— 逐步加 source 标签，不阻塞

### 工作量

| 类别 | 新增 LOC | 修改 LOC |
|------|---------|---------|
| 核心模块 | ~330 | ~150 |
| 测试 | ~400 | — |
| **合计** | **~730** | **~150** |

## §6 Phase C 备忘（不在本次范围）

以下功能记录在案，未来按需实现：

- **主动巡检 Agent** — 定时扫全校数据找异常 → agent_findings → 通知教师
- **跨 Agent 协作** — Agent A 输出作为 Agent B 输入的协议
- **Token 预算计费** — 按校/按用户 token 消耗统计 + 账单
- **增强模型用量统计** — 系统提供 Claude 的用量追踪
- **Redis session store** — 替代内存 dict，支持多进程部署
- **Warm session pool** — 减少首次对话冷启动延迟
- **Step resumption** — WorkflowEngine 步骤级故障恢复
