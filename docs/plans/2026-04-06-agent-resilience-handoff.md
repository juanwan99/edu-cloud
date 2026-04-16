---
type: handoff
created: 2026-04-06 20:02:43
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-06-agent-resilience-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-06-agent-resilience-plan.md
---

## 约束与偏好

**T3 流程。** Gate 1 Plan Review 3 轮通过（PASS with conditions）。

**Gate 1 残留条件（Executor 执行时修正）：**
1. Task 8 循环检测的行为级测试需走 AgentLoop 真实入口（非手写遍历逻辑）——GPT R3 指出测试仍是逻辑镜像
2. Contract Pack semantic_regression 的 temporal_trace oracle 需补 `trace_ref` 字段（指向 `docs/plans/oracles/` 下的 YAML）

**执行顺序严格：** P0-1 → P0-2 → P0-3 → P0-4 → P1-1 → P1-2 → P2-1+P2-2 → P2-3 → P3-1 → P3-2 → 全量回归。P2 验证增强依赖 P0-1（接线修复后验证才生效）。

**已有 1359 tests，每批次后跑全量回归。** 测试框架 pytest，conftest 提供 db_engine/admin/school fixtures。

**双模型共识点（不可偏离）：**
- P0-1 改 runtime 消费侧（不改 agent_loop 的 SSE 载荷格式）
- P0-4 按 turn 计（非按单工具），全部失败才递增 tool_fail_streak
- P1-1 先做 chat()，chat_stream() 延期
- P1-2 用 ToolSpec.is_read_only 区分超时值（只读 30s / 写入 60s）
- P2-3 跳过时复用现有 tool_result 事件形状，不新增事件类型

## 启动 Prompt

```
[edu-cloud] Executor | 2026-04-06 20:02:43
项目: C:\Users\Administrator\edu-cloud  读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-06-agent-resilience-handoff.md，按 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-06-agent-resilience-plan.md Task 1-11 执行。使用 executing-plans skill。完成后输出审查交接单。使用 codex-review skill 进行 GPT 代码审查。
```
