---
type: handoff
created: 2026-04-13 19:47:33
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-biz-replication-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-phase1-plan.md
---

## 项目背景（新窗口零上下文假设）

### 这是什么项目
`edu-cloud` 是多校协同云端教育平台（FastAPI + Vue 3 + Naive UI，79 表，1918+ 后端 tests，端口 9000）。当前在复刻 `haofenshu-clone`（Nuxt 3 + Element Plus + Express + SQLite，8 业务模块 × 45 前端页面）的业务骨架，补齐 edu-cloud 缺失的 4.5 个模块。

### 当前阶段
**Phase 1 / Batch 2 (Frontend 骨架) / 待执行**

3 批次拆分（plan §「批次拆分」）：
- Batch 1: Schema + Menu API（Task 1-3）— ✅ **Gate 2 R2 PASS** (commit `ef8a32a`，详见下方 §Batch 1 R2 PASS 摘要)
- Batch 2: Frontend 骨架（Task 4-9）← **本批次**
- Batch 3: Frontend 完善（Task 10-12）

### Batch 2 范围（plan Task 4-9）
- T4: Nuxt 3 项目初始化（`frontend-nuxt/`，Element Plus，Vue Router，Pinia）
- T5: auth store + middleware（access_token / refresh_token 双 token 拦截）
- T6: useApi composable（统一请求/错误处理）
- T7: useMenus composable + 导航组件（消费 `GET /api/v1/menus`）
- T8: 三种 Layout（默认/登录/简洁）
- T9: login + home 页面（含模块卡片网格）

### Batch 2 独立 Gate（F008 R2，不依赖 Task 12）
1. Nuxt dev 启动无报错（`npx nuxt dev --port 3000`）
2. POST `/api/v1/auth/login` 拿到 access_token
3. 访问 `/home` 渲染模块卡片
4. 点击模块跳转到子页面（即使是 Task 9 的占位页）

完整命令见 plan 头部「Batch 2 独立验证命令」段（行 21-32）。

## §Batch 1 R2 PASS 摘要（启动前必读）

| 维度 | 结果 |
|------|------|
| GPT Codex R2 结论 | **PASS** |
| Commit | `e64957a` (R2 修复) → `ef8a32a` (gates.json + R2 报告 + raw log) |
| F001 | HIGH test-gap defect_fix → **resolved-correct verified** (6 migration 方言中立化, smoke 3/3) |
| F002 | MED design-concern behavior_change **approved** → resolved-correct (conduct_admin_router 28 端点纳入 Batch 1) |
| F003 | HIGH test-gap defect_fix → resolved-correct verified (反证独立复现) |
| R2-F001（新） | LOW design-concern defect_fix → 不阻塞（见下方处置） |
| 本地验证 | tests/test_alembic_migration.py + tests/test_menu/ 12/12 PASS |
| Gate 回执 | `code_review_batch1.status=pass`, `report_path=docs/plans/2026-04-12-haofenshu-phase1-review-report-batch1-r2.md` |

### R2-F001 处置（本批次注意点）

**finding**: 上一批 R2 交接单声称「5 个全量回归 failures 全部 pre-existing」，但 GPT 今日只能稳定复现 2 个（`tests/test_ai/test_tool_access_fail_closed.py::{test_no_capability_record_rejects, test_partial_capability_match_rejects}`），其余 3 个 flaky 用例两侧对照都 PASS。**不指向 R2 回归**，不阻塞 Gate。

**Batch 2 处理方式**: 
- Batch 2 完成后跑全量回归时，若仍出现这 2 个稳定 failure，可在审查交接单中收窄表述为「2 个稳定 pre-existing 已确认 + 3 个 flaky 用例本轮未复现」，避免再次复制「5 failures pre-existing」表述。
- 不需要在 Batch 2 修复这 2 个 ai/tool_access fail-closed 测试（与本批次无关，属于另一议题）。

## 约束与偏好（design 未记录的增量）

- **任务级别**: T4（跨前后端 + 多 Batch + 4 Gate 流程）。本会话开始声明 `[T4] haofenshu Phase 1 Batch 2 — Frontend 骨架`。
- **流程**: T4 流程（Planner 调度 + Executor 执行 + GPT Codex 审查）。本批次为 Executor 角色。
- **下一窗口角色**: Executor（执行 Task 4-9）— 不是 Planner、不是 Reviewer。
- **审查载体（执行后产出）**:
  - 审查交接单：`docs/plans/2026-04-12-haofenshu-phase1-review-handoff-batch2.md`
  - codex-review 由 Planner 在新窗口调度（不在 Executor 会话中跑）
- **Windows 环境铁律**:
  - 用 `python` 不用 `python3`（env-guard hook 硬拦截）
  - `cd` 用 Bash 工具（Windows Git Bash 环境）
  - 端口 9000 已被 edu-cloud 后端占用；Nuxt dev 独占 3000（前端 5273 是 Vue 3 Vite，不要混淆）
  - 服务启动必须通过 `~/.claude/scripts/serve.py`（port_guard hook 硬拦截）
- **工作树状态注意**:
  - `git status` 显示大量未提交 M/?? 文件（Conduct/KG/AI 模块未 commit 的工作残留），**与 Batch 2 无关**。Batch 2 只新建 `frontend-nuxt/` 目录，避免触碰这些残留。
  - `git stash list` 中有一条 `pre-batch2 GraphPanel color tweaks (orphaned — GraphPanel being removed)` — **不要 pop**，无关。
- **scope_guard 注意**: Batch 2 commit 必须严格在 Task 4-9 声明的范围内（plan 已列出每个 Task 的「文件清单」段）。Batch 2 主要新建 `frontend-nuxt/` 目录及子文件；不修改 Batch 1 已落盘的后端文件（src/edu_cloud/modules/menu/* / alembic/versions/*）。
- **Tier 升级提醒**: 新窗口启动 codex-review / writing-plans / handoff-card / reconciliation 等 T3+ skill 时，session_guard 会要求 effective_tier=T3/T4。先在 CLAUDE.md 声明 `[T4] {描述}` 或直接写 SessionState `effective_tier=T4`。
- **L017 意图守卫**: Batch 2 若审查产出 behavior_change finding，禁止批量批准（必须逐条「批准 F00X / 拒绝 F00X」）。
- **PASS 报告锚定**: Gate 2 多轮审查时，gates.json `report_path` 必须指向最终 PASS 版本（不可保留早期 FAIL 报告路径）。

## 启动 Prompt（复制到新窗口）

```
[edu-cloud] Executor (Phase 1 Batch 2 — Frontend 骨架) | 2026-04-13 19:47:33
项目: C:\Users\Administrator\edu-cloud

读取交接卡: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-haofenshu-phase1-batch2-handoff.md
读取 Plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-phase1-plan.md（重点 Task 4-9 + 头部「Batch 2 独立验证命令」段）
读取 Design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-biz-replication-design.md
读取 Batch 1 R2 PASS 报告: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-phase1-review-report-batch1-r2.md
读取 gates.json: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-phase1-gates.json

声明：[T4] haofenshu Phase 1 Batch 2 — Frontend 骨架（Nuxt 3 + Element Plus 项目骨架 + auth + menu 渲染）

任务（plan Task 4-9，按顺序执行）：
1. Task 4: Nuxt 3 项目初始化（frontend-nuxt/，含 Element Plus / Vue Router / Pinia / TS 配置）
2. Task 5: auth store + middleware（access_token / refresh_token 拦截 + 401 自动 refresh）
3. Task 6: useApi composable（统一 base URL / 错误处理）
4. Task 7: useMenus composable + 导航组件（消费 GET /api/v1/menus，按 role × module 双维过滤）
5. Task 8: 三种 Layout（default/auth/blank）
6. Task 9: login + home 页面（首页模块卡片网格）

每个 Task 完成后:
- 跑该 Task 「**审查清单**」段的验证命令
- 行为变更 Task 跑「**测试契约**」段定义的测试 slice
- 累计 commit 到 master（commit message 含 "T{N}" 标识 + 测试通过数）

完成所有 Task 4-9 后:
- 运行 plan 头部「Batch 2 独立验证命令」段（4 步：Nuxt dev 启动 / login API / /home 卡片 / 模块跳转）
- 跑 Batch 1 + Batch 2 全量回归（前端 vitest + 后端 pytest），输出失败列表
- **R2-F001 处置**: 若全量回归出现 `tests/test_ai/test_tool_access_fail_closed.py::{test_no_capability_record_rejects, test_partial_capability_match_rejects}` 失败，在审查交接单中表述为「2 个稳定 pre-existing 已确认（git stash R2 修改后同样复现）」，不要重复「5 failures pre-existing」表述（R2-F001 LOW design-concern）
- 输出审查交接单到 `docs/plans/2026-04-12-haofenshu-phase1-review-handoff-batch2.md`（按 ~/.claude/rules-t3/review-templates.md「审查交接单」格式）
- 必填：逐 Task 自审表 + 测试契约预审自检 + 验证清单自检 + 自查段（四要素）+ Batch 2 独立 Gate 4 步实测证据

工作树注意:
- 大量未提交 M/?? 文件与 Batch 2 无关（Conduct/KG/AI 模块残留），不要触碰
- git stash 有一条 GraphPanel 残留，不要 pop
- Batch 2 主要新建 frontend-nuxt/ 目录及子文件；scope_guard 会拦截 Batch 1 已落盘文件的修改

Windows 环境铁律：用 `python` 不用 `python3`；`cd` 用 Bash 工具；服务启动通过 ~/.claude/scripts/serve.py（port_guard 硬拦截）。

完成后输出审查交接单。
```

## 验证清单（本交接卡自检）

- ✅ plan 文件绝对路径存在: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-phase1-plan.md`
- ✅ design 文件绝对路径存在: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-biz-replication-design.md`
- ✅ Batch 1 R2 PASS 报告绝对路径存在: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-phase1-review-report-batch1-r2.md`
- ✅ gates.json 绝对路径存在: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-phase1-gates.json`
- ✅ 启动 Prompt 无 `<...>` 占位符、无 "as discussed" 类悬挂引用
- ✅ 启动 Prompt 末尾含 `完成后输出审查交接单。`（T4 格式）
- ✅ 任务级别 T4 已声明
- ✅ R2-F001 LOW finding 处置方式已明确（C1：本批次审查交接单中收窄表述）
- ✅ 工作树残留警告已包含（未提交 M/?? + git stash 不要 pop）
