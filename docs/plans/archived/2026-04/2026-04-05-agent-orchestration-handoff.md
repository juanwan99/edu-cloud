---
type: handoff
created: 2026-04-05 08:11:58
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-05-agent-evolution-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-05-agent-orchestration-plan.md
---

## 约束与偏好

**T4 流程**（设计→计划→Gate 1 Plan Review→执行→Gate 2 Code Review）

- **Gate 1 待通过**: `docs/plans/2026-04-05-agent-orchestration-gates.json` 中 plan_review 状态为 pending。执行前必须先通过 codex-review (plan) 审查。
- **向后兼容是硬约束**: 简单请求必须退化为现有单 AgentLoop，SSE 事件格式不能变。现有 1166 后端 + 72 前端测试全部通过才算完成。
- **并行执行模式留空**: Phase 1 只实现 sequential 执行，parallel/dag 是 Phase 1 完成后的增量。
- **sub-agent 不跑 TaskPlanner**: run_as_sub_agent 内 task_planning=False，避免递归规划。
- **模型 slot 映射**: enhanced=强模型(tier 1), primary=中等(tier 2), basic=弱模型(tier 3)，对应 llm-proxy 的 slot 名。
- **用户选择 subagent-driven-development**: 每个 Task 派发 subagent 执行，Task 间做 review。
- **测试运行**: 后端测试 `cd ~/edu-cloud && python -m pytest --tb=short -q`，AI 模块测试 `python -m pytest tests/test_ai/ -v`。

## 启动 Prompt

```
[edu-cloud] Executor | 2026-04-05 08:11:58
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-05-agent-orchestration-handoff.md，按 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-05-agent-orchestration-plan.md Task 1-9 执行。

执行前先运行 codex-review skill 对 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-05-agent-orchestration-plan.md 进行 plan review（Gate 1）。Gate 1 通过后，使用 subagent-driven-development skill 逐 Task 执行。完成后输出审查交接单。
```
