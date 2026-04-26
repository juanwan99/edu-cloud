---
type: handoff
created: 2026-03-29 22:35:52
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-29-phase1b-base-info-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-29-phase1b-base-info-plan.md
---

## 约束与偏好

**T3 流程** — Phase 1b 基础信息增强（排课表 + 选考组合），Gate 1 待审。

- 分支: `feat/frontend-role-aware`（沿用 Phase 1a 分支）
- Phase 1a 的 `_check_school_scope` 模式已在 code review R1 中被强化（`PermissionDeniedError` + `_CROSS_SCHOOL_ROLES` set）。本 phase 的两个 router 各自独立定义同模式的 scope guard
- `MANAGE_SCHOOL_SETTINGS` 权限复用 Phase 1a 已有的，不新增权限枚举
- conftest.py 中 `async_session` monkey-patch 已就位（Phase 1a 加入），中间件测试无需额外处理
- 用户选择 Subagent-Driven 执行方式

## 启动 Prompt

```
[edu-cloud] Executor | 2026-03-29 22:35:52
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-03-29-phase1b-base-info-plan.md，
按 Task 1-7 逐一执行。使用 executing-plans skill。
完成后输出审查交接单。

Gate 1: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-29-phase1b-gates.json (plan_review: pending)
分支: feat/frontend-role-aware
Topic: phase1b

先使用 codex-review skill 进行 GPT 计划审查（Gate 1），通过后再执行。
完成后输出审查交接单。使用 codex-review skill 进行 GPT 代码审查。
```
