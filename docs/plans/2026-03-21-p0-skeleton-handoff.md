---
type: handoff
created: 2026-03-21 23:16:48
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-21-super-platform-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-21-p0-skeleton-plan.md
---

# P0 骨架 — 执行交接卡

## 约束与偏好

**T3 流程**（跨文件、有接口变更、需要设计决策）

1. **执行方式**: Subagent-Driven Development（用户已确认）。每个 Task 派发独立 subagent，任务间 review。
2. **前端从零开始**: edu-cloud 当前无任何前端代码，frontend/ 目录需要创建。
3. **后端 58 tests 不可回归**: RBAC 重构（Task 3）涉及 deps.py 返回值变更，计划中已列出全部受影响文件。Permission 枚举保留旧值兼容。
4. **GPT 5.4 是唯一 Codex 模型**: codex exec 不指定 -m 参数（默认 gpt-5.4）。禁止用 o3/gpt-4.1 等。
5. **路线 A 单体重构**: edu-cloud 整体重写为统一平台，不是 BFF 模式。AI Agent 内建（不独立服务）。
6. **暗色主题**: 前端使用 Naive UI darkTheme。
7. **成绩分布按得分率分段**: 不是固定分数段，适配不同满分的考试。

## 启动 Prompt

```
[edu-cloud] Executor | 2026-03-21
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-03-21-p0-skeleton-handoff.md，
按 C:\Users\Administrator\edu-cloud\docs\plans\2026-03-21-p0-skeleton-plan.md Task 1-8 执行。
使用 superpowers:subagent-driven-development skill。
完成后输出审查交接单。使用 codex-review skill 进行 GPT 代码审查。
```
