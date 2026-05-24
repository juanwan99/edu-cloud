# Agent 引擎剩余 Gap 消除计划 (v5 — R1-R4 修正)

> 基于双模型审查 + 3 路调研 agent + GPT R1/R2/R3 三轮审查修正

## 基线

- 后端: 609 passed / 2 failed (spike, 预期)
- 前端: 2368 passed
- 工具: 65 个 @edu_tool
- 生产: mcu.asia → 330a0ce
- Alembic: 单 HEAD `185f6c3280b9` (已验证)

## 铁律

**绝对禁止破坏已有正常功能。** 每步改动前全量调查依赖，改动后跑全量测试验证无回归。

## 三轮 GPT 审查修正追踪

| 轮次 | Finding | 验证 | 修正 |
|------|---------|------|------|
| R1 | models.py 4处生产引用 | **确认** | 从删除清单移除 |
| R1 | workflow/ 8处生产引用 | **确认** | 从删除清单移除 |
| R1 | grounded.py 被 runtime.py:11 引用 | **确认** | 条件删除（F5+9a 后） |
| R1 | budget_final_json 未写入 | **确认** | Step 8 补 plumbing |
| R1 | capabilities=None 语义冲突 | **确认** | 跳过检查而非全放行 |
| R1 | card_layout 签名不等价 | **否决** | — |
| R1 | Alembic 多 HEAD | **否决** | 实际单 HEAD |
| R2 | runtime.py import 闭包 | **确认** | Step 9a 先改 cli/agent.py |
| R2 | card_auto_layout 需 parsed_questions | **确认** | Step 5 加参数 |
| R2 | budget plumbing 缺失 | **确认** | Step 8 新增 set_budget_snapshot |
| R2 | datetime 时区 | **确认** | UTC+8 aware |
| R3 | helpers 不能从旧模块 import | **确认** | 提取到 modules/card/ |
| R3 | run_id unique 冲突（resume flush） | **确认** | resume 不重复写 trace header |
| R3 | 旧测试 import runtime 需清理 | **确认** | Batch D 明确包含 |
| R4 | resume 跳 trace flush 丢事件 | **确认** | flush_to_db 加 append_only 模式 |
| R4 | grep 范围漏 tests/ | **确认** | 补 tests/ 到验证 grep |
| R4 | budget set_budget 保存引用混淆 initial/final | **确认** | set 时冻结 initial dict |
| R4 | semantic_regression 漏 sessions/card 端点 | **确认** | 补充完整 |

---

## Step 1: N2 — 空消息返回 422（极低风险）

**文件**: `src/edu_cloud/api/ai.py:125-128`

**改动**: `return {"error": str(e)}` → `raise HTTPException(status_code=422, detail=str(e))`

**依赖检查**: 前端 `aiChat.js:48-51` 已处理 `!resp.ok` → 读 `errBody.detail`。无其他调用方。

**验证**: 后端 609 + 前端 2368

---

## Step 2: T2 — SSE Queue 集成测试（零风险）

**文件**: 新建 `tests/test_ai/test_engine/test_sse_queue.py`

**测试用例**:
1. `test_queue_drain_receives_all_events`
2. `test_queue_drain_handles_agent_error`
3. `test_task_cancel_on_generator_exit` — 验证取消路径跳过 trace flush 的行为

**验证**: 新测试全通过 + 现有 609 无回归

---

## Step 3: spike 测试修复（零风险）

**文件**: `tests/test_ai/test_pydantic_ai_spike.py`

**改动**: 对 `test_gate2_streaming` 和 `test_full_integration` 加 xfail（只屏蔽 ModelHTTPError，不屏蔽本地确定性回归）

**验证**: 2 fail → 0 fail

---

## Step 4: F4 — filter_tools_for_role 加 capabilities（低风险）

**文件**: `tools/__init__.py` + `api/ai.py`

**改动**: 增加 `capabilities` 参数。`None` = 跳过检查（before_tool 兜底），非"全放行"。`api/ai.py` 传入已加载的 capabilities dict。

**验证**: 后端 609 + health tools=65

---

## Step 5: F5 — card_layout 桥接清理（中风险，R3 重设计）

### R3 阻断修正

**问题**: 旧 `tools/card_layout.py` 顶层 `import registry, ToolContext`，从该模块 import helper 函数会触发旧引擎 import 链。且 `card/router.py:169,409` 也直接 import 这些 helpers。

**解决方案 — 提取 helper 到 card 模块**:

1. **新建** `src/edu_cloud/modules/card/layout_helpers.py`:
   - 从 `tools/card_layout.py` 提取纯函数: `calculate_layout`, `_load_layout`, `_save_layout`, `_apply_to_regions`
   - 这些函数只依赖文件系统 + json，不依赖 ToolContext/registry

2. **更新** `card/router.py:169,409`:
   - `from edu_cloud.ai.tools.card_layout import ...` → `from edu_cloud.modules.card.layout_helpers import ...`

3. **重写** `engine/tools/card_layout.py`:
   - `card_auto_layout(ctx, subject_id, parsed_questions)` — 内联 Subject 查询 + 调用 `layout_helpers.calculate_layout`（R2 修正: 加 parsed_questions）
   - `card_adjust_layout(ctx, subject_id, adjustments)` — 同理
   - 不再 import ToolContext 或旧 tools

4. **不删除旧文件** — 旧 `tools/card_layout.py` 本步保留（旧测试仍引用），Step 9 统一清理

### 验证

1. `grep "from edu_cloud.ai.tool_context\|from edu_cloud.ai.tools.card_layout" src/edu_cloud/ai/engine/ src/edu_cloud/modules/card/router.py` → 零命中
2. `python -c "from edu_cloud.modules.card.layout_helpers import calculate_layout"` → 无旧引擎 import 触发
3. 后端 609 + 前端 2368

---

## Step 6: D2 — ArtifactManager DB 持久化（中风险）

**改动**: `artifact_manager.py` 新增 `async flush_to_db(db_sessionmaker)`

- 遍历 `_artifacts` → 写入 `AiArtifact`（ORM + migration 已有）
- try/except + logger.warning（和 TraceRecorder 模式一致）
- `raw_data` 不持久化（表只存 summary/preview 元数据）

**调用位置**:
- 正常路径 `run()` 结尾（trace flush 之后）
- resume 路径 `resume_after_confirmation()` 结尾

**R3+R4 修正 — resume flush_to_db unique 冲突 + 事件不丢失**:
- `AiAgentTrace.run_id` 是 unique
- `run()` 已写入 trace header + 清空 events
- `resume_after_confirmation()` 产生新 events（confirmation_resolved 等）
- **修复**: `TraceRecorder.flush_to_db(append_only=False)` 新增参数：
  - `append_only=False`（默认）: 创建 trace header + 写入 events（run() 路径）
  - `append_only=True`: 查询已有 trace header，只追加新 events（resume 路径）
- resume 路径调用 `trace.flush_to_db(db_sessionmaker, append_only=True)` — events 不丢失且无 unique 冲突

**验证**: 后端 609 + 发消息触发 artifact 确认 DB 写入

---

## Step 7: D1 — ConfirmationBroker 审计事件（低风险）

**改动**: `edu_runtime.py` 的 `resume_after_confirmation()` 中 approve/deny 后:
```python
self._deps.trace.record_event("confirmation_resolved", {
    "confirmation_id": cid, "decision": "approve"/"deny",
})
```

不创建新 DB 表。审计事件通过现有 TraceRecorder → ai_agent_trace_event 持久化（在 run() 结尾的 flush_to_db 中一并写入）。

**验证**: 后端 609

---

## Step 8: D3 — 日请求限制 + budget 快照（中风险）

### Phase A: budget 快照写入（R2+R3 修正）

`trace_recorder.py` 新增方法（R4 修正 — 分离 initial 快照 vs final 引用）:
```python
def set_budget(self, budget) -> None:
    # R4: set 时冻结 initial 为不可变 dict，flush 时从 budget 引用读 final
    self._budget_initial = {"max_tokens": budget.max_tokens, "max_tool_calls": budget.max_tool_calls}
    self._budget_ref = budget  # mutable 引用，flush 时读最终计数器
```

`flush_to_db()` 写入时:
```python
if self._budget_initial:
    trace.budget_initial_json = json.dumps(self._budget_initial)
if self._budget_ref:
    trace.budget_final_json = json.dumps({
        "used_tokens": self._budget_ref.used_tokens,
        "used_tool_calls": self._budget_ref.used_tool_calls,
    })
```

### Phase B: 日请求次数限制

`api/ai.py` 在构建 Runtime 前查询 `ai_agent_trace` 当日 count:
- UTC+8 日界 → UTC aware 查询（R2 修正）
- 软限制（体验级限流，非计费/安全硬限制）
- 配置: `school_settings` KV `ai_daily_chat_limit` (默认 100)

**验证**: 后端 609 + 新增日限制测试

---

## Step 9: C1 — 旧引擎安全清理（高风险，最后执行）

### 前置条件

1. Step 5 完成 — engine + card/router.py 不再 import 旧 tools/card_layout.py 或 tool_context.py
2. Step 9a 完成 — cli/agent.py 改用新引擎

### Step 9a: 更新 cli/agent.py

`cli/agent.py:26` 当前 import 旧 `AgentRuntime`（Phase C 占位 CLI）。
改为 import `EduAgentRuntime`，适配参数。

### 必须保留（不可删除）

| 文件/目录 | 生产引用 |
|----------|---------|
| `anonymizer.py` | api/ai.py + engine |
| `data_scope.py` | api/ai.py + engine |
| `memory_injector.py` | api/ai.py |
| `memory_store.py` | api/ai.py + engine |
| `prompts.py` | api/ai.py + worker.py |
| `ref_resolvers.py` | api/ai.py:109 |
| `ref_types.py` | api/ai.py:96 |
| `schemas.py` | engine |
| `models.py` | app.py:84 + alembic/env.py:30 + db_doctor.py:87 |
| `workflow/` | app.py:188 + worker.py:32 |
| `__init__.py` | 包入口 |
| `engine/` | 新引擎 |

### 可安全删除（9a + F5 完成后）

**旧引擎核心** (24 文件):
```
runtime.py, grounded.py, tool_context.py,
agent_loop.py, agent_spec.py, agent_team.py,
audit.py, capability_probe.py, context_manager.py,
entity_extractor.py, intent_router.py,
llm_adapter.py, memory_extractor.py,
model_router.py, registry.py,
scoped_query.py, scope_version.py,
sensitivity_router.py, session_memory.py,
shared_state.py, supervisor.py,
task_planner.py, tool_access.py, tool_executor.py
```

**旧目录**: `teams/` (4 文件: __init__.py, edu_data.py, homework.py, knowledge.py — R3 修正文件数)

**旧工具**: `tools/` 全部 23 文件（helpers 已提取到 modules/card/layout_helpers.py）

### 删除流程（R2+R3 修正）

1. **Step 9a**: 更新 cli/agent.py（单独 commit + 全量测试）
2. **每个待删文件**: `grep -rn "edu_cloud.ai.{module}" src/ scripts/ alembic/ tests/`（R4: 含 tests/）
3. 分 4 批：
   - **Batch A**: 零引用文件 (audit.py)
   - **Batch B**: 叶子文件 (entity_extractor, intent_router, scope_version 等)
   - **Batch C**: 核心链 (runtime → supervisor → agent_loop → llm_adapter 等) + grounded + tool_context
   - **Batch D**: 旧工具目录 + teams/ + **旧测试文件**（R3: 明确包含 test_runtime.py 等引用旧引擎的测试）
4. **每批后验证** (R2+R3 修正):
   - `python -c "from edu_cloud.api.app import create_app"` (app 启动 smoke)
   - `python -c "from edu_cloud.worker import WorkerSettings"` (worker smoke)
   - `python -c "from edu_cloud.cli.agent import parse_args"` (cli smoke)
   - pytest 全量（PASS 数减少但 0 个 PASS→FAIL）

---

## Step 10: P3 — 超时分级

**改动**: ConfirmationBroker 构造时按 risk_level 传 timeout（low=120s, medium/high=300s）。

OutputValidator/PreBudgetCheck/TierPromotion 不在本次 scope（设计文档未定义或 P3 级别）。

---

## 测试基线跟踪

| 步骤 | 后端预期 | 前端预期 |
|------|---------|---------|
| 基线 | 609p/2f | 2368p |
| Step 1-4 | 612p+/0f | 2368p |
| Step 5-8 | 615p+/0f | 2368p |
| Step 9 | ~570p/0f | 2368p |
| Step 10 | ~570p/0f | 2368p |

## semantic_regression

不变量:
- POST /api/v1/ai/chat SSE 事件格式不变
- POST /api/v1/ai/runs/{id}/confirmations/{id} 端点签名不变
- GET /api/v1/ai/health 返回 tools=65 不变
- GET /api/v1/ai/ref-types + /refs 端点不变
- GET /api/v1/ai/sessions + DELETE /api/v1/ai/sessions/{id} 端点不变 (R4 补充)
- 65 个 @edu_tool 注册不变
- PolicyToolGuardrail fail-closed 不变
- 保留组件 (anonymizer/data_scope/memory_*/prompts/schemas/ref_*/models/workflow) 不删
- app.py / worker.py / alembic/env.py import 链不断
- cli/agent.py 改用新引擎后 importability 不断
- card_auto_layout 输入契约: subject_id + parsed_questions
- card/router.py 端点功能不变 (editor-layout/auto-layout/parse-answers/preview-by-weights) (R4 补充)
- card/router.py layout helper 功能不变（提取到 modules/card/layout_helpers.py）
- 日请求限制: UTC+8 日界 → UTC 查询
- budget snapshot: initial 冻结于 set 时，final 从引用读取 (R4 修正)
- resume trace: append_only=True 追加事件不重建 header (R3+R4 修正)
