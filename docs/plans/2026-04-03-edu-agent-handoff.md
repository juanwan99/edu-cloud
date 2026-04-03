---
type: handoff
created: 2026-04-03 16:01:52
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-edu-agent-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-edu-agent-plan.md
---

## 约束与偏好

**T4 流程。** 需经过 Gate 1 (codex-review plan) 后方可执行。

- 用户明确要求"质量第一，可维护性很重要，把基础打扎实"——不接受 shortcuts
- 激进替换策略：直接重写 ai/ 模块，不做并行共存。开发阶段无线上用户，无回归风险
- 工具接口标准化是本次最大的 breaking change：39 个工具全部从 `**kwargs` 改为 `(input: dict, ctx: ToolContext) -> ToolResult`
- llm-proxy (port 8100) 已存在且可用，Agent 通过 slot 调用，不直连任何 LLM API
- 现有测试 1037 个（后端），改造完必须全绿
- 用户的商业模式是七天网络式：学校免费 + 家长付费。Agent 内核同时服务教师端和（未来的）家长端
- 双通道路由安全原则：碰过 student 数据的会话锁定到主通道（国产模型），绝不流向增强通道

## 启动 Prompt

```
[edu-cloud] Planner | 2026-04-03 16:01:52
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-edu-agent-handoff.md，按 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-edu-agent-plan.md 执行。

这是 T4 流程。先执行 codex-review skill 对 plan 进行 Gate 1 审查。Gate 1 通过后，使用 subagent-driven-development skill 逐 Batch 执行 Task 1-30。每个 Batch 完成后输出审查交接单。
```
