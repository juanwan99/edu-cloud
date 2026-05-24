# Agent Phase 2 — 价值牵引的韧性底座

> 双模型共识方案（Claude 审计 + GPT 独立评估）
> 策略：每做一个用户可见场景，同时补齐它依赖的可靠性

## 基线

- 后端: 2321 passed / 2 failed (governance hook) / 2 xfailed
- 前端: 2368 passed
- 工具: 65 个 @edu_tool
- 生产: mcu.asia → 055cf86
- Alembic: 单 HEAD `185f6c3280b9`
- 引擎: Pydantic AI 1.94.0 + 4 层 RBAC + SSE + 写确认 + trace 双写

## 铁律

**绝对禁止破坏已有正常功能。** 每步改动前全量调查依赖，改动后跑全量测试验证无回归。

## 现状诊断（三路审计 + GPT 独立评估）

| 维度 | 现状 | 核心缺口 |
|------|------|---------|
| 引擎核心 | ★★★★☆ 成熟 | 无重大缺口 |
| 生产韧性 | ★★☆☆☆ | 会话内存存储、LLM 无熔断、消息不持久 |
| 业务价值 | ★★☆☆☆ | 65 工具仅 5 action、无页面集成、workflow 与 chat 隔离 |

## 5 Sprint 路线图

```
Sprint 1: 会话持久化 + LLM 韧性    （韧性底座）
Sprint 2: 页面上下文 AI 入口        （感知价值跃升）
Sprint 3: 批量 action + 通知联动    （工作流助手）
Sprint 4: Workflow-Agent 融合       （杠杆最大化）
Sprint 5: 前端体验增强              （闭环 UX）
```

---

## Sprint 1: 会话持久化 + LLM 韧性（韧性底座）

### S1-T1: 消息持久化（双表 + API）

**背景**: 当前会话历史在内存 `_sessions` dict 中，进程重启全部丢失。`AiSession` 模型已定义但从未写入。

**改动**（R1 F-001/F-002 修正 — 复用 AiSession 做会话目录 + 新增消息子表）:

1. **激活 `AiSession`** (`models/ai_session.py:5-11`): 已有字段（user_id, role, school_id, context_snapshot, messages）满足会话目录需求
   - `ai_chat` 端点创建/恢复 session 时写入 `AiSession` 记录
   - `GET /api/v1/ai/sessions` 改为查 DB（当前查内存）
   - `DELETE /api/v1/ai/sessions/{id}` 同步删 DB 记录

2. **新建 `AiChatMessage` 子表**:
   ```
   ai_chat_messages 表:
     id (UUID PK)
     session_id (String36, FK→ai_sessions.id, idx)
     role_in_chat (String20)  -- 'user' | 'assistant'
     content (Text)
     metadata_json (Text)     -- tools/confirmations/thinking/refs
     created_at (DateTime)
   ```

3. **Alembic migration**: `down_revision='185f6c3280b9'`（只建 ai_chat_messages，AiSession 表已存在）

4. **写入时机**: `edu_runtime.py` 的 `run()` 完成后，将 user message + assistant response 写入 DB

5. **读取 API**: `GET /api/v1/ai/sessions/{id}/messages?page=1&page_size=20`
   - 返回分页消息列表（倒序）
   - Owner 隔离（和现有 session 端点一致）

6. **启动恢复**: `ai_chat` 端点中，session_state 创建时从 DB 加载最近 N 条消息作为 history

**不改**:
- `_sessions` 内存 dict 仍保留作为热缓存（性能）
- 现有 SSE 流不变
- 前端暂不改（Sprint 5 加历史 UI）
- `AiToolCall` 模型保留（未来可用于工具级审计，当前不写入）

**非目标**（R1 F-007 声明）: 进程重启后 pending confirmation 不可恢复——确认卡有 5 分钟超时，重启后自然过期，前端显示"已超时"。

**验证**: 后端全量 + 新增 4 个持久化测试（会话创建/消息写入/读取/分页）

### S1-T2: LLM 重试 + 熔断

**背景**: `edu_runtime.py:130` 每次请求创建新 `AsyncOpenAI` 客户端，无重试、无熔断。LLM proxy 502 时请求直接失败。

**改动**:

1. **按 model_slot 缓存 OpenAI 客户端**（R1 F-003 修正 — 单例会丢 X-LLM-Slot header）:
   ```python
   _llm_clients: dict[str, AsyncOpenAI] = {}
   def get_llm_client(slot: str) -> AsyncOpenAI:
       if slot not in _llm_clients:
           _llm_clients[slot] = AsyncOpenAI(
               base_url=LLM_PROXY_BASE,
               api_key="unused",
               default_headers={"X-LLM-Slot": slot},
               max_retries=2,
               timeout=httpx.Timeout(180.0, connect=10.0),
           )
       return _llm_clients[slot]
   ```

2. **EduAgentRuntime._build_model()**: 接收 client 参数而非每次创建
   ```python
   def _build_model(self, client: AsyncOpenAI | None = None) -> OpenAIChatModel:
       ...
   ```

3. **熔断**: 简单计数器，连续 3 次 LLM 失败后 30s 内直接返回 503
   - 在 api/ai.py 层实现（不侵入 runtime）
   - `_llm_circuit = {"failures": 0, "open_until": 0}`

4. **SSE 友好错误**: LLM 不可用时 yield `AgentEvent(type="error", data={"message": "AI 服务暂时不可用，请稍后重试", "retryable": True})`

**不改**: 工具内部的 DB 查询不加重试（已有 SQLAlchemy 连接池重连）

**验证**: 后端全量 + mock LLM 502 测试

### S1-T3: ~~清理 AiSession/AiToolCall~~ → 取消（R1 F-002/F-010 修正）

**原计划**: 删除 `AiSession`/`AiToolCall` 死代码。
**取消原因**: S1-T1 已激活 `AiSession` 做会话目录，`AiToolCall` 保留供未来工具级审计。不再是死代码。

---

## Sprint 2: 页面上下文 AI 入口（感知价值跃升）

### S2-T1: AiSlidePanel 上下文注入

**背景**: AiSlidePanel 只接收 `visible` prop，无法接收页面上下文。

**改动**:

1. **新增 prop**: `initialContext: { type: String, label: String, refs: Array }`
   ```vue
   const props = defineProps({
     visible: { type: Boolean, default: false },
     initialContext: { type: Object, default: null },
   })
   ```

2. **上下文提示**: 打开面板时如果有 `initialContext`，在输入框上方显示上下文卡片
   ```
   📊 当前上下文: 高二期中考试 · 数学
   [移除]
   ```

3. **发送时自动附加**: `sendMessage` 时如果有 context，自动作为 refs 传入

4. **AppShell 传递**: 通过 provide/inject 或 Pinia store 传递当前页面上下文

**不改**: aiChat store 逻辑不变，只是 refs 来源多了一个

### S2-T2: ExamDetailPage AI 按钮

**背景**: 考试详情页是最高频页面，当前无 AI 入口。

**改动**:

1. **在 ExamDetailPage 的 Tab 栏右侧加 AI 按钮**: "AI 分析本考试"
2. 点击后打开 AiSlidePanel，预填上下文:
   ```js
   aiContext.value = {
     type: 'exam_analysis',
     label: `${exam.name} · ${subject.name}`,
     refs: [{ type: 'exam', id: exam.id, label: exam.name }],
     suggestedPrompt: '请分析这次考试的整体情况',
   }
   ```
3. **suggestedPrompt**: 面板打开时自动填入输入框（用户可修改后发送）

**验证**: 前端 vitest + 手动验证 mcu.asia

### S2-T3: AnalyticsReportPage AI 诊断按钮

**改动**: 同 S2-T2 模式，在分析报告页加 "AI 深度诊断" 按钮
- 预填 refs: 当前选中的考试 + 科目
- suggestedPrompt: "请对这次考试做全面诊断分析"

**验证**: 前端 vitest

---

## Sprint 3: 批量 Action + 通知联动（工作流助手）

### S3-T1: 批量补救作业工具

**背景**: 教师发现 C 类学生后需要手动逐个布置作业。新增批量工具。

**新工具**: `assign_remedial_homework`
```python
@edu_tool(
    name="assign_remedial_homework",
    module_code="homework",
    is_read_only=False,
    risk_level="medium",
)
async def assign_remedial_homework(
    ctx: RunContext[AgentDeps],
    exam_id: str,
    subject_id: str,
    score_threshold: float,
    homework_title: str,
    homework_content: str,
) -> str:
    """为低于阈值的学生批量布置补救作业。"""
```

**流程**:
1. 查询低于阈值的学生列表
2. 生成预览（N 个学生，列出姓名）
3. 通过 ConfirmationBroker 确认（medium risk → 300s）
4. 确认后批量创建 HomeworkTask + HomeworkSubmission

**不新建**: 复用现有 HomeworkTask/HomeworkSubmission 模型

**验证**: 后端全量 + 新工具单测

### S3-T2: 通知草稿工具

**新工具**: `draft_parent_notification`
```python
@edu_tool(
    name="draft_parent_notification",
    module_code="conduct",
    is_read_only=False,
    risk_level="high",
)
async def draft_parent_notification(
    ctx: RunContext[AgentDeps],
    student_ids: list[str],
    subject: str,
    template: str = "score_alert",
) -> str:
    """为指定学生家长生成通知草稿（不发送，存入 Studio 待审批）。"""
```

**流程**: 生成 Studio Document (draft 状态) → 教师在 Studio 审批后发送
- 高风险：需要 ConfirmationBroker 确认
- 不直接发送通知：走 Studio Document 审批流

**验证**: 后端全量

---

## Sprint 4: Workflow-Agent 融合（杠杆最大化）

### S4-T1: Workflow 查询工具（R1 F-006 修正 — 扩展现有工具，不新建）

**背景**: W1/W3/W6 产出的 agent_findings/agent_tasks 对聊天 agent 不可见。

**改动**: 扩展 `misc.py` 中现有的 `get_findings`/`get_agent_tasks` 工具:
- 增加 `since_hours` 参数（默认 24h，查最近异常）
- 增加 `include_details` 参数（返回 finding 详情而非摘要）
- 增加 `severity_filter` 参数（只看 HIGH/CRITICAL）

**不新建工具**: 避免近义工具语义冲突

### S4-T2: Workflow 触发工具（R1 F-004/F-005 修正 — EventBus 路径 + adapter 设计）

**新工具**: `trigger_exam_analysis`
```python
@edu_tool(
    name="trigger_exam_analysis",
    module_code="analytics",
    is_read_only=False,
    risk_level="low",
)
async def trigger_exam_analysis(
    ctx: RunContext[AgentDeps],
    exam_id: str,
) -> str:
    """触发考后分析流水线（W1），生成快照/报告/诊断。"""
```

**流程**（R1 F-004 修正 — W1 走 EventBus 不走 arq）:
1. 从 AgentDeps 获取 db_sessionmaker → 开 session
2. 构造 WorkflowContext（school_id 从 deps.school_id，trigger_ref=exam_id）
3. 调用 WorkflowExecutor.execute(W1_POST_EXAM, ...)
4. 幂等（idempotency_key = `w1_post_exam_{exam_id}`）
5. 返回 run status（completed/already_exists/failed）

**AgentDeps → WorkflowContext 桥接**（R1 F-005 修正）:
```python
async def _agent_to_workflow_ctx(deps: AgentDeps, exam_id: str) -> WorkflowContext:
    """从 AgentDeps 构造 WorkflowContext，用于在 chat 工具中触发 workflow。"""
    return WorkflowContext(
        db_sessionmaker=deps.db_sessionmaker,
        school_id=deps.school_id,
        trigger_ref=exam_id,
        run_id=deps.run_id,
    )
```
放在 `engine/tools/actions.py` 中，供 workflow 触发工具使用。

### S4-T3: Prompt 融合 — Workflow 上下文注入

**改动**: `build_teacher_prompt()` 新增 Workflow 引导段:
```
## 可用的后台分析
系统定期自动分析：
- 考后分析（W1）：考试发布后自动生成成绩快照、班级报告、异常检测
- 学生画像（W3）：每日更新知识掌握度、错误模式、成长轨迹
- 异常巡检（W6）：每小时扫描阅卷超时、低提交率、成绩异常

当教师询问分析类问题时，优先使用 get_recent_findings 查看已有结果，
避免重复计算。如果没有现成结果，可触发 trigger_exam_analysis。
```

---

## Sprint 5: 前端体验增强（闭环 UX）

### S5-T1: 对话历史 UI

**改动**: AiSlidePanel 顶部加 "历史" 按钮，打开历史侧边栏
- 调用 `GET /api/v1/ai/sessions`（S1-T1 已改为查 DB）列出历史会话
- 点击会话 → 调用 `GET /api/v1/ai/sessions/{id}/messages` 加载消息 → 恢复对话

**验证**: 前端 vitest + 手动验证历史加载/恢复

### S5-T2: Artifact 内联预览

**改动**: 当 assistant 消息中有 `_artifact` 引用时，渲染预览卡片
- 表格型: 显示前 5 行 + "查看全部"
- 文档型: 显示摘要 + "在 Studio 中打开"

**验证**: 前端 vitest（mock artifact 数据）

### S5-T3: 上下文面包屑

**改动**: 面板顶部显示当前对话的上下文链
```
高二期中考试 → 数学 → 班级对比分析
```
- 从 refs 和 tool_call 历史自动推导

**验证**: 前端 vitest

---

## 测试基线跟踪

| Sprint | 后端预期 | 前端预期 |
|--------|---------|---------|
| 基线 | 2321p/2f | 2368p |
| S1 | 2330p+/2f | 2368p |
| S2 | 2330p+/2f | 2375p+ |
| S3 | 2340p+/2f | 2375p+ |
| S4 | 2350p+/2f | 2375p+ |
| S5 | 2350p+/2f | 2385p+ |

## semantic_regression

不变量:
- POST /api/v1/ai/chat SSE 事件格式不变
- POST /api/v1/ai/runs/{id}/confirmations/{id} 端点签名不变
- GET /api/v1/ai/health 返回 tools 数量（增长但不减少）
- 65 个现有 @edu_tool 注册不变（只增不减）
- PolicyToolGuardrail fail-closed 不变
- 保留组件 (anonymizer/data_scope/memory_*/prompts/schemas/ref_*/models/workflow) 不删
- app.py / worker.py / alembic/env.py import 链不断
- W1/W3/W6 workflow 定时执行不受影响
- 前端 AiSlidePanel 现有功能不回归（SSE/tools/confirmation/refs）
- ExamDetailPage 现有 Tab 功能不变（只加 AI 按钮）

## 风险模块（R1 F-009 补充）

| 文件 | 风险 | 原因 | Sprint |
|------|------|------|--------|
| src/edu_cloud/api/ai.py | HIGH | 核心端点，会话管理 + 新 API + 熔断 | S1 |
| src/edu_cloud/ai/engine/edu_runtime.py | HIGH | LLM 客户端重构 | S1 |
| src/edu_cloud/models/ai_session.py | HIGH | 激活已有模型，涉及 app.py/alembic import 链 | S1 |
| src/edu_cloud/worker.py | MED | S4 Workflow 触发可能影响定时任务 | S4 |
| src/edu_cloud/ai/workflow/engine.py | MED | WorkflowContext 桥接 | S4 |
| src/edu_cloud/ai/engine/tools/misc.py | MED | 扩展现有工具参数 | S4 |
| src/edu_cloud/ai/engine/tools/actions.py | MED | 新增 workflow adapter | S4 |
| src/edu_cloud/ai/prompts.py | MED | prompt 变更影响所有对话 | S4 |
| frontend/src/components/ai/AiSlidePanel.vue | MED | 上下文注入 + 历史 UI | S2/S5 |
| frontend/src/pages/ExamDetailPage.vue | MED | 页面集成 | S2 |
| Alembic migration | MED | 新表 | S1 |

## 执行节奏

- 每 Sprint 独立可交付（commit + build + deploy 验证）
- Sprint 1-2 同会话串行（韧性 + 首个可见场景）
- Sprint 3-5 可按业务优先级调整顺序
- 每 Sprint 结束 GPT code review（T3 gate）
