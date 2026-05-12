<!-- no-projectctl -->
# Agent Pydantic AI 重构交接文档

=== 生成块开始 ===
task_id: T3-agent-pydantic-ai-rebuild
topic: agent-pydantic-ai-rebuild
project_dir: ~/projects/edu-cloud
effective_tier: T3
gate_status: {plan_review: pass, code_review: pending}
last_verified_evidence: 66 passed on clean tree 2bf8a00; E2E Playwright screenshot ai-panel-new-engine-e2e.png; health tools=65
subject_hash: 2bf8a00
raw_output_hashes: N/A
timestamp: 2026-05-12 19:45:00
created: 2026-05-12 19:45:00
=== 生成块结束 ===

=== 自由备注开始 ===

> Design: `docs/plans/2026-05-12-agent-optimization-design-v2.md`
> Session: 本会话完成设计文档 8 步全量实施 + E2E 验证

---

## Goal

用 Pydantic AI 替代自建的 AgentLoop/Supervisor/ToolRegistry 管线，保留 edu-cloud 自建的安全壳（RBAC/DataScope/Budget/Confirmation/Artifact/Trace）作为差异化护城河。

**一句话：Pydantic AI 做引擎，edu-cloud 做教育安全壳。**

---

## Must Preserve

- `engine/` 目录是唯一活跃后端路径：`api/ai.py` → `EduAgentRuntime` → Pydantic AI Agent → `@edu_tool`
- 65 个工具的 `@edu_tool` 装饰器自动执行 `before_tool()` / `after_tool()` / artifact 处理 / SSE 事件推送——**不要手动调用这些方法**
- `PolicyToolGuardrail` 是 fail-closed 设计：注册层 RBAC 过滤 + 调用层 4 层硬检查。两层都存在，不可删一留一
- `asyncio.Queue` 事件推送机制：tool_wrapper 推事件 → edu_runtime 后台 task + queue drain → SSE 实时输出。这个模式解决了 `agent.run()` 是同步调用无法中间 yield 的问题
- 前端 SSE 事件格式兼容：`thinking` / `tool_call` / `tool_result` / `confirmation_required` / `answer` / `done`
- `DataScope` / `MemoryStore` / `Anonymizer` / `prompts.py` / `schemas.py` 是被新引擎引用的保留组件，不要随旧引擎一起删

## Must Not Change

- `POST /api/v1/ai/chat` 的 SSE 事件格式——前端 `sseParser.js` + `aiChat.js` 依赖这个契约
- `POST /api/v1/ai/runs/{run_id}/confirmations/{confirmation_id}` 端点签名——前端 `resolveConfirmation()` 依赖
- `EduToolMeta` 的 frozen 设计——工具元数据注册后不可变
- `AgentDeps.get_db()` 返回独立 session 的模式——每个工具独立事务，解决旧架构共享 session 并行被禁用的问题
- 确认超时 5 分钟（`DEFAULT_TIMEOUT = 300.0`）——教师课堂打断是常态

---

## Commits

| Hash | Message |
|------|---------|
| `84c70fe` | feat: rebuild AI Agent on Pydantic AI — full 8-step engine replacement (50 files, +4855/-403) |
| `6406905` | feat: add 5-minute confirmation timeout — backend 410 + frontend countdown |
| `2bf8a00` | fix: health endpoint reports full tool count via collect_all_tools() |

---

## Architecture

```
POST /api/v1/ai/chat (api/ai.py)
  ├─ DataScopeBuilder.build()           ← 保留组件
  ├─ collect_all_tools() + filter_tools_for_role()
  ├─ build_teacher_prompt() + MemoryInjector  ← 保留组件
  └─ EduAgentRuntime(...)
       ├─ AgentDeps (identity + scope + infra)
       ├─ PolicyToolGuardrail (role/module/capability/scope)
       ├─ AgentBudget (token/tool/write/wall-clock)
       ├─ Pydantic AI Agent(model=OpenAIChatModel → llm-proxy:8100)
       │   └─ 65 @edu_tool functions
       │       ├─ tool_wrapper: before_tool → exec → artifact → after_tool
       │       └─ asyncio.Queue: push tool_call/tool_result events
       ├─ ConfirmationBroker (write pause → SSE → POST resume)
       ├─ ArtifactManager (>32KB/50row → redacted summary)
       └─ TraceRecorder (JSONL + DB dual-write)

POST /api/v1/ai/runs/{run_id}/confirmations/{id}
  └─ find runtime by run_id → check expiry → approve/deny → resume agent
```

## File Map

```
src/edu_cloud/ai/engine/          ← 新引擎（3208 行）
  agent_deps.py                   ← RunContext 依赖容器
  edu_runtime.py                  ← 顶层编排（构建 → 运行 → SSE 翻译）
  policy_guardrail.py             ← 4 层安全硬检查
  budget.py                       ← 请求级预算控制
  confirmation_broker.py          ← 写确认（内存版）
  artifact_manager.py             ← 大结果脱敏
  trace_recorder.py               ← JSONL + DB 双写
  tool_meta.py                    ← 工具元数据
  tool_wrapper.py                 ← @edu_tool 装饰器 + TOOL_META_REGISTRY
  tools/                          ← 65 个原生工具（16 模块文件）
    __init__.py                   ← collect_all_tools() + filter_tools_for_role()
    students.py (4), exams.py (3), analytics.py (2), analytics_score.py (5),
    analytics_compare.py (3), analytics_report.py (3), knowledge.py (4),
    profile.py (4), grading_ops.py (3), bank.py (2), homework.py (5),
    conduct.py (8), card_layout.py (3), misc.py (12), actions.py (2),
    artifact_query.py (2)

src/edu_cloud/ai/                 ← 旧引擎（生产路径已切断，保留供旧测试）
  data_scope.py                   ← ★ 被新引擎引用
  memory_store.py                 ← ★ 被新引擎引用
  memory_injector.py              ← ★ 被 api/ai.py 引用
  anonymizer.py                   ← ★ 被新引擎引用
  prompts.py                      ← ★ 被 api/ai.py + worker.py 引用
  schemas.py                      ← ★ 被新引擎引用（AgentEvent）
  runtime.py                      ← 旧入口，生产不调用
  supervisor.py / agent_loop.py / tool_executor.py  ← 旧管线
  registry.py / tool_context.py / tool_access.py    ← 旧注册
  llm_adapter.py / capability_probe.py / model_router.py  ← 旧路由
  tools/ (23 files, 63 tools)     ← 旧工具，生产不调用

tests/test_ai/test_engine/        ← 新引擎测试（904 行，55 tests）
tests/test_ai/test_pydantic_ai_spike.py  ← spike 验证（5 gates）

frontend/src/
  utils/sseParser.js              ← +confirmation_required 事件
  stores/aiChat.js                ← +pendingConfirmations + resolveConfirmation()
  components/ai/AiSlidePanel.vue  ← +确认卡片 UI + 倒计时 + 超时态

DB: ai_artifacts + ai_agent_trace + ai_agent_trace_event（migration 185f6c3280b9）
```

---

## Verified Evidence

| 维度 | 证据 |
|------|------|
| 后端测试 | 66 passed on clean tree `2bf8a00` |
| 前端测试 | 2357 passed (108 test files) |
| 工具注册 | health endpoint → `{"tools": 65}` |
| 前端 build | `version.json` → `git_hash: 84c70fe, dirty: false` |
| E2E | Playwright 截图 `ai-panel-new-engine-e2e.png`：发送"高一期中考试有哪些科目" → 查询 4 个数据源 → 返回 11 科目表格 |
| 生产路径 | `grep` api/ + worker.py 旧组件引用 = 零命中 |
| 远程推送 | `ba847f2..2bf8a00 master -> master` |

---

## Open Gaps（按优先级）

### P0 — 影响 Agent 回答质量

| ID | 缺口 | 说明 | 改动范围 |
|----|------|------|---------|
| **F1** | DOMAIN_KNOWLEDGE 未注入 | 设计 §5.8 要求备课教研/考后分析/学生追踪三大场景方法论注入 system prompt。当前只有通用准则，agent 在复杂教学场景缺少方法论引导 | `prompts.py` 加 ~30 行 |

### P1 — 影响可靠性或完整性

| ID | 缺口 | 说明 | 改动范围 |
|----|------|------|---------|
| **D1** | ConfirmationBroker 无 DB | 纯内存，进程重启丢失 pending 确认 | 新 ORM model + broker 升级 |
| **D2** | ArtifactManager 无 DB | 纯内存，跨会话 artifact 查询不可用 | ai_artifacts 表写入 |
| **F3** | 前端 410 超时未特殊处理 | `resolveConfirmation()` 不区分 410 vs 其他错误 | `aiChat.js` ~5 行 |
| **T1** | AiSlidePanel 无组件测试 | 确认卡片/倒计时/超时/清理全无自动化 | 新测试文件 |

### P2 — 改善但不阻塞

| ID | 缺口 | 说明 |
|----|------|------|
| **F4** | RBAC 注册层未过滤 capabilities | `filter_tools_for_role()` 只检查 role+module，capabilities 靠 before_tool() 兜底（fail-closed，不越权但工具列表冗余） |
| **F5** | card_layout 桥接旧 ToolContext | 2 工具 import 旧 `ToolContext`，功能正常但违反"不欠技术债"原则 |
| **D3** | AgentBudget 无日额度 | 设计标注 P1 的 user/school daily quota 完全缺失 |
| **T2** | SSE Queue 无集成测试 | asyncio.Queue drain 模式未被 test_edu_runtime 覆盖 |
| **C1** | 旧引擎 ~40 文件未清理 | 10 个"删除"文件紧耦合（runtime→supervisor→agent_loop 链），需原子删除 |

---

## Risks

| 风险 | 缓解 |
|------|------|
| llm-proxy 不支持 SSE streaming | agent.run() 同步模式可用，streaming 需 llm-proxy 侧修复 |
| 进程重启丢失 pending 确认 | 单进程部署可接受；多实例前必须做 D1 |
| 旧引擎文件误导后续开发者 | 文件头加 deprecated marker 或整批移入 _deprecated/ |
| card_layout 桥接旧 ToolContext | 旧 tool_context.py 不可删直到 F5 完成 |

---

## Next Session Recommendation

1. **F1**（DOMAIN_KNOWLEDGE 注入）— 最高 ROI，~30 行改动直接提升 agent 教学场景表现
2. **F3**（前端 410 处理）— ~5 行改动
3. **D1 + D2**（DB 持久化）— 中等工作量，需 ORM + migration
4. **T1**（AiSlidePanel 测试）— 防止确认卡片回归

=== 自由备注结束 ===
