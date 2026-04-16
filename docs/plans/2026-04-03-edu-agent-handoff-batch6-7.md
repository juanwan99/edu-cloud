---
type: handoff
created: 2026-04-03 22:04:43
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-edu-agent-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-edu-agent-plan.md
---

## 约束与偏好

**T4 流程。** 本批次覆盖 Batch 6（工具迁移）+ Batch 7（集成+清理），是 edu-agent 的收尾阶段。

### Batch 1-5 已落地的关键实现细节

1. **registry.py 双签名兼容**（INV-001）：`_is_new_style()` 自动检测工具签名。旧 `**kwargs` 工具和新 `(input: dict, ctx: ToolContext) -> ToolResult` 工具共存。Batch 6 将 39 个工具逐个迁移到新签名，迁移完成后双签名逻辑仍保留（安全兜底）。

2. **AgentLoop 已完成**（Task 13）：`agent_loop.py` 是核心循环，协调所有模块。SSE 事件格式已通过契约测试（Task 14）与旧 `agent.py` 对齐（INV-004）。

3. **SSE 事件格式铁律**（INV-004，Batch 5 R2 修复）：
   - `tool_call` 事件：不含 `id` 字段（旧格式兼容）
   - `tool_result` 事件：`result` 是原始 dict（不是 ToolResult wrapper）
   - 前端 `stores/aiChat.js` 的 SSEProcessor 依赖这些精确字段名

4. **F003 accepted-risk**（Batch 5 R3）：多 task plan 的综合总结功能延迟到 Task 27（API 集成）处理。当前 AgentLoop 在 plan 执行完后不自动生成总结 message。

5. **tool_access.py 同步化**：三层过滤已从 async 改为 sync（Batch 1），API 层调用时不需要 await。

6. **GPT 审查共计**：5 轮 PASS，发现 6 code-bug + 9 test-gap，全部修复。当前 228 tests 全绿。

### Batch 6 特别注意

- 39 个工具分布在 12 个文件中（tools/*.py），每个文件独立 commit
- 每个工具的改造是机械性的：签名改 `(input: dict, ctx: ToolContext) -> ToolResult` + 参数从 `input` dict 解包 + 返回值包装 ToolResult + try/except
- **sensitivity 分配规则**：
  - `student` 工具（含学生姓名/成绩/画像）：students.py, bank.py, profile.py
  - `school` 工具（含学校级数据）：exams.py, analytics*.py, homework.py, grading_ops.py, knowledge_db.py, actions.py
  - `public` 工具（不含任何学校/学生数据）：knowledge.py（课标/教材/真题搜索）
- 迁移后旧测试 `test_tools_*.py` 需要适配新签名（`tools.execute(name, args, ctx)` 替代 `tools.execute(name, args, _db=db, ...)`）

### Batch 7 特别注意

- Task 27（API 集成）：替换 `api/ai.py` 中的旧 Agent 为 AgentLoop。旧 pipeline（IntentResolver → ModelRouter → create_llm_for_tier → Agent.run）替换为新 pipeline（CapabilityProbe → ToolAccessResolver → SensitivityRouter → AgentLoop.run）。同时处理 F003 accepted-risk（plan 综合总结）。
- Task 28（删除废弃文件）：删除 agent.py, llm.py, llm_factory.py, model_router.py, intent_resolver.py, context.py 及其旧测试。
- Task 29（Alembic migration）：agent_memories 表。
- Task 30（全量集成测试）：全部测试通过 + 39 工具注册数验证。

## 启动 Prompt

```
[edu-cloud] Executor | 2026-04-03 22:04:43
项目: C:\Users\Administrator\edu-cloud  读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-edu-agent-handoff-batch6-7.md，按 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-edu-agent-plan.md Task 15-30 执行。使用 executing-plans skill。完成后输出审查交接单。
```
