---
type: handoff
created: 2026-04-13 11:26:31
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-module-governance-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-module-governance-plan.md
---

## 约束与偏好（design/plan 未记录的增量）

**Tier**: T3 流程（必须新会话执行；Gate 2 强制；Task 8 Gate 2 PASS 后再跑）

- **Gate 1 已 PASS（R4 contested）**：审查报告 `docs/plans/2026-04-13-module-governance-plan-review.md`，R4 的 F008/F009 标为 `resolved-false-positive`（GPT 把 Plan Review 当 Code Review 做，检查文件物理存在属 Gate 2 范畴）。Gate 2 会重新把关实质落地，contested 不绕过 Gate 2。
- **方法论铁律（R1-R4 教训）**：治理类任务严禁"凭印象/叙述"下结论——对齐 commit_guards 契约前必须 `sed -n '60,120p' ~/.claude/hooks/commit_guards.py` 读真实 staged_info 构造（`{"files": [...], "diff": "..."}`，不是 `{paths, stats}`）。Task 4/5 MODULE.md 的 owns_tables / owns_routes / depends_on 字段一律以 Step 1 grep 的真实代码为准，禁止预设 "grading=调度 / pipeline=执行" 这类叙述。
- **自愈式纪律**：Task 6 `check_new_module` 只对"HEAD 不含的目录"block；存量模块（HEAD 有）缺 MODULE.md 走 `check_touched_legacy` 软 ask——这是自愈式收敛的核心，不可为"纯净度"升级为 block。
- **P0 调研由 Opus 亲自执行**（不委派 subagent）：机械扫描只缩候选，判定必须读代码 + git log 交叉验证（L013 防御）。清单条目每条须含原文摘录 + 调用方 + 判定 + 建议，用户只 approve/reject/defer 不做 triage。
- **commit 纪律**：每个 Task 独立 commit（小步快跑），避免上次事故（本会话 plan commit 意外打包 conduct 改动）。`git add` 一律指定文件路径，禁止 `git add .` / `git add -A`。
- **KILL_SWITCH**：hook 上线后若误报卡死开发，`export EDU_GOVERNANCE_GUARD_DISABLED=1` 紧急禁用（Task 6 Step 3 实现）。
- **全局 CLAUDE.md 已预埋**：用户已在 `~/.claude/CLAUDE.md:25-27` 加入 commit_guards + module_governance_guard 条目——Task 8 Step 2 只需追加安全铁律条目，不必重复。

## 启动 Prompt

```
[edu-cloud] Executor | 2026-04-13 11:26:31

项目: C:\Users\Administrator\edu-cloud

读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-module-governance-handoff.md 的约束与偏好。
按 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-module-governance-plan.md 的 Task 1→7 顺序执行。

流程:
- Task 1 (P0 基线调研): Opus 亲自读代码 4 批次（paper/scan/pipeline/grading/marking/card → knowledge/adaptive/analytics/bank/homework → exam/school/studio/conduct/student/profile/menu/calendar → services/ai/api 横切层），产出带证据的债务清单 docs/governance/edu-cloud-module-baseline-2026-04-13.md；用户逐批 approve/reject/defer 后进 Task 2
- Task 2-3: MODULE.md 模板 + 聚合脚本（含 CLI 入口 subprocess 测试）
- Task 4-5: grading + pipeline MODULE.md 试点（Step 1 grep 真实 __tablename__ / APIRouter prefix / import 后填写，禁止预设边界）
- Task 6: module_governance_guard.py 含 parse_diff_line_counts / check_new_module (git evidence + parse_module_md 校验) / check_ownership_conflicts / check_touched_legacy / check_derived_products_fresh / _LoaderError 传播 / check 入口
- Task 7: 接入 ~/.claude/hooks/commit_guards.py 的 CHECKS 列表追加 module_governance_guard.check；手动验证 3 场景写入 docs/plans/.module-governance-hook-verify.log

使用 superpowers:executing-plans skill。

Gate 1 已 PASS（R4 contested resolved-false-positive，理由见 docs/plans/2026-04-13-module-governance-plan-review.md）。
Task 8 暂不执行——留待 Gate 2 Code Review PASS 后再做 CLAUDE.md 回写 + [实现完成] 标记。

全部 Task 完成后输出审查交接单（写入 docs/plans/2026-04-13-module-governance-review-handoff-batch1.md 并 commit）。使用 codex-review skill 进行 GPT 代码审查。
```
