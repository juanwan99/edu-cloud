---
type: handoff
created: 2026-04-04 18:12:27
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-04-agent-evolution-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-04-agent-evolution-plan.md
---

## 约束与偏好

**T4 流程。** 计划已经过 GPT 3 轮 Plan Review（R1: 6 findings, R2: 4 findings, R3: 3 findings，全部修复），Gate 1 PASS。

1. **执行方式：** 用户选择 Subagent-Driven（superpowers:subagent-driven-development）。每 Task 派独立 subagent，主线程 review between tasks。

2. **批次结构（6 批，20 Tasks）：**
   - B1 基础设施（T1-T4a-T4b-T5）：8 新表 + DataScope + ScopedQuery + fail-closed + scope version
   - B2 W1 考后分析（T6-T10）：WorkflowEngine + 5 步后台 + 3 域工具 + EventBus
   - B3 W3 学情画像（T11-T13）：mastery 增量 + 画像趋势 + 家长 Persona
   - B4 W6 异常巡检（T14-T15）：3 种巡检 + 去重限流 + 异常域工具
   - B5 IntentRouter（T16-T17）：关键词规则 + 实体槽位 + 工具注册
   - B6 集成收尾（T18-T19）：api/ai.py 串联 + arq cron + E2E

3. **GPT 审查节奏（T4 流程）：** 每批次完成后输出审查交接单，由 Planner 调度 codex-review (code)。B1 是地基批次，所有后续批次依赖它。

4. **关键 GPT 审查修正（已反映在计划中）：**
   - Task 4 拆为 4a（parent 权限）+ 4b（fail-closed 改造）
   - Task 5 scope version 用 DB 持久化（scope_versions 表），不用进程内存
   - Task 18 测试用 mock/spy 验证 DataScopeBuilder + IntentRouter 被调用
   - Task 18 parent fixture 依赖 `seed_school`，函数名 `create_access_token`
   - Task 1 包含 8 张表（含 scope_versions），test_alembic_migration.py 需更新

5. **现有代码库关键信息：**
   - 测试 fixture：`seed_school`（返回 school, secret）、`admin_user`、`teacher_headers`、`subject_teacher_headers`
   - auth：`create_access_token`（非 create_token）、返回字段 `access_token`（非 token）
   - 当前角色：`current["current_role"]`（非 user.active_role_id）
   - 工具签名：`async def(input: dict, ctx: ToolContext) -> ToolResult`
   - Pipeline 表：`modules/profile/models.py`（snapshots + mastery）、`modules/bank/models.py`（error_books）
   - EventBus：`core/events.py`，`event_bus.on("exam.published")`

6. **gates.json 位置：** `C:\Users\Administrator\edu-cloud\docs\plans\agent-evolution-gates.json`
7. **state.json 位置：** `C:\Users\Administrator\edu-cloud\docs\plans\agent-evolution-state.json`

## 启动 Prompt

```
[edu-cloud] Executor | 2026-04-04 18:12:27
项目: C:\Users\Administrator\edu-cloud  读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-04-agent-evolution-exec-handoff.md，按 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-04-agent-evolution-plan.md 全部 Task 执行。使用 superpowers:subagent-driven-development skill。完成每批次后输出审查交接单。
```
