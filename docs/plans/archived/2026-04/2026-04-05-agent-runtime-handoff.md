---
type: handoff
created: 2026-04-05 23:03:14
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-05-agent-runtime-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-05-agent-runtime-plan.md
---

## 约束与偏好

**T3 流程**（设计→计划→Gate 1 Plan Review→执行→Gate 2 Code Review）

- **Gate 1 待通过**: `docs/plans/2026-04-05-agent-runtime-gates.json` 中 plan_review 状态为 pending。执行前必须先通过 codex-review (plan) 审查。
- **Phase 1+2 已完成**: 多 Agent 编排引擎 + 跨会话记忆系统已交付（1409+ tests）。本次在此基础上加 AgentRuntime 层。
- **api/ai.py 迁移要谨慎**: Task 8 是最高风险——瘦身重构不能破坏 SSE/session/profile。必须跑全量回归。
- **OutputValidator 不调 LLM**: 纯正则+数值比对。这是硬约束，不是建议。
- **现有 42 个工具不改**: source 标签逐步迁移，不在本次范围。ToolResult.source 默认 None 保证向后兼容。
- **Worker/CLI 只留接口**: 定时任务的具体实现（哪个学校启用、具体 prompt）留 Phase C。本次只确保 AgentRuntime 能被 Worker/CLI 调用。
- **两层模型是商业设计**: 主力模型用户自备（DeepSeek），增强模型系统提供（Claude 中转，付费）。基础版用户 enhanced_enabled=False，Agent 必须能完全独立运行。
- **pre-existing test failures**: test_tool_access_fail_closed.py 有 2 个历史遗留失败（capability deny-only vs fail-closed 不一致），与本次无关。
- **用户选择 subagent-driven-development**: 每个 Task 派发 subagent 执行。

## 启动 Prompt

```
[edu-cloud] Executor | 2026-04-06 07:00:00
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-05-agent-runtime-handoff.md，按
C:\Users\Administrator\edu-cloud\docs\plans\2026-04-05-agent-runtime-plan.md Task 1-9 执行。

执行前先运行 codex-review skill 对 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-05-agent-runtime-plan.md 进行 plan
review（Gate 1）。Gate 1 通过后，使用 subagent-driven-development skill 逐 Task 执行。完成后输出审查交接单。
```
