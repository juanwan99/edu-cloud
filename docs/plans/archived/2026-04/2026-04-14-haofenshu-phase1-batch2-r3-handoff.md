---
type: handoff
created: 2026-04-14 08:10:39
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-biz-replication-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-phase1-plan.md
independent_fix_design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-14-auth-fail-closed-repair-design.md
r2_fail_report: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-phase1-review-report-batch2-r2.md
r2_handoff: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-phase1-review-handoff-batch2-r2.md
---

# haofenshu-phase1 Batch 2 R3 修复交接卡

> Planner → Executor
> 前置：Code Review R2 FAIL（authoritative report 2026-04-14 07:35:32，Planner L013 独立复现证据）
> gates.json 修正：commit `f539a5f`（raw_output_hash 指向 authoritative FAIL log + 双审查 audit trail）

---

## §0 R3 上下文速览

### R2 最终结论（authoritative）
- **B2-F001 contested**（MED code-bug）：`npm ci --ignore-scripts` exit 0 但稳定产生 **EBADENGINE Unsupported engine** 警告 6+ 条。lockfile 锁的 dep（`nitropack@2.13.3` / `@rollup/plugin-alias@6.0.0` / `ast-kit@2.2.0` / `chokidar@5.0.0` / `magic-string-ast@1.0.3` / `rollup-plugin-visualizer@7.0.1` 等）要求 Node `>=20.19.0` 或 `>=22.12.0`，当前 Node `v20.18.0` 不满足。
- **B2-F002 verified**（MED code-bug）：AuthError 职责分层已完整实现，4 ORC + 3 反证成立。R3 不触碰。
- **B2-F003 contested**（LOW design-concern）：handoff §6 "原表述" 引用块仍保留 "WSL 后端 hot-reload 失效" 原文。LOW 单独不阻塞 Gate，但用户批准**顺手收窄**。

### R3 修复路径（用户 2026-04-14 已批准）
- **方案 A**: 升级 Node floor 到 `>=22.12.0`（behavior_change，用户已 approved）
- **顺手 X**: 删除 handoff line 171 的 "WSL 后端 hot-reload 失效" 旧措辞引用

### 非 R3 scope
- ❌ 不降级任何 npm dep 版本（方案 B 已 rejected）
- ❌ 不改 AuthError / useMenus / default.vue 任何逻辑（B2-F002 verified，不碰）
- ❌ 不启动 Batch 3（Task 10-12）——R3 PASS 后单独交接

---

## §1 约束与偏好（design.md / plan.md 未记录的增量）

### 1.1 Tier 与角色

**Tier**: **T4**（延续 Batch 2 R1→R2→R3 同一 T4 轨道）

**新窗口角色**: **Executor**。修复 → 产出 R3 审查交接单 → 后续 Planner 调度 codex-review R3。

会话开始**必须声明**：`[T4] haofenshu Phase 1 Batch 2 Gate 2 Code Review Round 3 — 修复 B2-F001 (Node floor upgrade) + B2-F003 (handoff 措辞清理)`

### 1.2 B2-F001 R3 修复铁律（behavior_change，用户已批准方案 A）

**Fix Intent Card（Executor 必须在 R3 交接单中填写）**:

```yaml
root_cause: frontend-nuxt/package-lock.json 锁定的多个 dep（nitropack/unplugin/ast-kit/chokidar/rollup-plugin-visualizer/magic-string-ast/@rollup/plugin-alias 等）要求 Node >=20.19.0 或 >=22.12.0 runtime；当前仓库/CI/dev 未声明 Node floor，环境里 Node v20.18.0 不满足 → `npm ci --ignore-scripts` 稳定产生 EBADENGINE 警告
preserved_invariants:
  - INV-01: 不修改现有 frontend/
  - INV-02: 不碰后端 src/edu_cloud/ 和 alembic/
  - INV-AUTH-01~04: B2-F002 已过的 4 ORC（auth-fail-closed / menu-degrade / auth-state-consistency / no-double-logout）不得回归
  - package-lock.json 当前 dep 版本不变（只升 Node floor, 不降/升 dep）
non_goals:
  - 不降级任何 dep（方案 B 已 rejected）
  - 不新增任何 dep
  - 不改 AuthError / useMenus / default.vue / auth.ts 任何逻辑
  - 不启动 Batch 3
allowed_change_surface:
  - frontend-nuxt/package.json（新增 "engines": {"node": ">=22.12.0"}）
  - frontend-nuxt/.nvmrc（新建，内容如 22.12.0 或更高具体版本）
  - 可选: frontend-nuxt/.npmrc（engine-strict=true，可选严格化）
  - 可选: 项目根 .nvmrc（若仓库级 Node 版本约束合理）
  - CLAUDE.md（追加 Batch 2 R3 进度行）
  - docs/plans/2026-04-12-haofenshu-phase1-review-handoff-batch2-r2.md（B2-F003 顺手清理：删除 line 171 "WSL 后端 hot-reload 失效" 引用段或重构 §6 before/after 不引用旧措辞）
verification:
  - 在 Node >=22.12.0 环境下 `cd frontend-nuxt && npm ci --ignore-scripts` → exit 0 **且** 零 EBADENGINE 警告
  - `npm ls @nuxt/kit @nuxt/schema commander crossws --depth=2` → 零 invalid / 零 extraneous
  - `./node_modules/.bin/vitest.cmd run` → 24/24 PASS 稳定
  - 反证：临时把 package.json engines 字段改为 `">=20.18.0"` → 不影响 npm ci 行为（engines 是声明性），但文档声明不再锁定现代 Node → 记录现状
semantic_risk: true
oracle:
  - ORC-NODE-01 (temporal_trace): clean `npm ci --ignore-scripts` 在满足 engines 的环境下 stdout/stderr 零 EBADENGINE warning
  - ORC-NODE-02 (forbidden_strategy): 不得通过降级 dep 版本达成零警告（禁止方向）
```

### 1.3 Node 版本选择细则

- **最低版本：`22.12.0`**（满足 nitropack/unplugin 的 `^20.19.0 || >=22.12.0` 以及 rollup-plugin-visualizer `>=22` 的上限）
- `.nvmrc` 建议值：`22.12.0` 或更高 LTS（如 `22.14.0` / `v22.12.0`，一行无 `v` 前缀即可）
- `package.json` engines 字段写 `">=22.12.0"`（兼容 22.14+，不锁定小版本）
- **禁止**使用 Node 20.x 范围（20.19+ 不够 rollup-plugin-visualizer 的 `>=22`）

### 1.4 Executor 环境预检

在开始修改前，**必须先在命令行确认当前 Node 版本**：
```bash
node --version
```

若当前环境是 Node 20.x，需要**切换到 22.12+** 再做验证（否则 npm ci 验证无意义）。切换方式（任选）：
- `nvm-windows` 用户：`nvm install 22.12.0 && nvm use 22.12.0`
- `fnm` / 其他版本管理：参考工具文档
- 无版本管理：从 https://nodejs.org 下载 Node 22.12+ LTS 手动安装

如果无法切换 Node 环境，**停止并向 Planner 报告**（不可降级 dep 或弱化验证标准）。

### 1.5 B2-F003 顺手收窄（方案 X）

**修改范围**：`docs/plans/2026-04-12-haofenshu-phase1-review-handoff-batch2-r2.md` §6

**操作**：
- 直接删除 line 170-171 `**原表述** (R1 交接单 Step 3/4)：` + `> Step 3/4 端到端受 WSL 后端 hot-reload 失效阻塞` 整段
- 保留 line 173-174 `**新表述** (R2 收窄)：...`（直接作为定论）
- 或：把 §6 标题由 "B2-F003 措辞收窄（本交接单吸收）" 改为 "B2-F003 根因定论"，移除对比段落，直接陈述 R2 结论
- 目标：handoff 全文 grep 不到 `WSL.*hot-reload` 或 `hot-reload.*失效`

**不修改**：其他段落（§1-§5 / §7+）保持原样。

### 1.6 scope_guard 边界

R3 commit 必须严格在以下目录：
- `frontend-nuxt/package.json` / `frontend-nuxt/.nvmrc` / `frontend-nuxt/.npmrc`
- 可选 项目根 `.nvmrc`（若决定仓库级约束）
- `frontend-nuxt/package-lock.json`（若 `npm ci` 触发细微 lockfile resolved URL 变更）
- `docs/plans/2026-04-12-haofenshu-phase1-review-handoff-batch2-r2.md`（B2-F003 顺手）
- `CLAUDE.md`（Batch 2 R3 进度行追加）
- `docs/plans/2026-04-14-haofenshu-phase1-review-handoff-batch2-r3.md`（R3 审查交接单新建）

**禁止触碰**：
- `frontend/`（INV-01）
- `src/edu_cloud/` / `alembic/`（INV-02）
- 任何 `frontend-nuxt/composables/` / `layouts/` / `stores/` / `tests/` 的 .ts/.vue 文件（B2-F002 verified 不动）
- `package-lock.json` 主动重装/重建（仅允许 `npm ci` 触发的可追溯小改）

### 1.7 Windows/env 铁律（继承）
- 用 `python` 不用 `python3`（env_command_guard 硬拦截）
- `cd` 用 Bash 工具
- 服务启动通过 `~/.claude/scripts/serve.py`（port_guard）
- 端口 9000（后端）/ 3000（Nuxt dev）

### 1.8 Tests 要求

R3 完成后必须跑：
1. `node --version` 确认 `v22.12.0` 或更高
2. `cd frontend-nuxt && rm -rf node_modules && npm ci --ignore-scripts 2>&1 | tee /tmp/npm-ci-r3.log`
3. `grep -c EBADENGINE /tmp/npm-ci-r3.log` → 期望 **0**
4. `npm ls @nuxt/kit @nuxt/schema commander crossws --depth=2 2>&1 | grep -cE "invalid|extraneous"` → 期望 **0**
5. `npx nuxt prepare` → 期望 exit 0
6. `./node_modules/.bin/vitest.cmd run` → 期望 **24/24 PASS**（与 R2 基线一致，不引入回归）
7. `grep -c "hot-reload" docs/plans/2026-04-12-haofenshu-phase1-review-handoff-batch2-r2.md` → 期望 **0**

所有 7 项断言必须**全部通过**才能产出 R3 审查交接单。

### 1.9 R3 审查交接单

路径：`C:\Users\Administrator\edu-cloud\docs\plans\2026-04-14-haofenshu-phase1-review-handoff-batch2-r3.md`

必填段落（按 `~/.claude/rules-t3/review-templates.md` 审查交接单格式）：
- 逐 Task 自审（B2-F001 R3 engines + .nvmrc 变更逐项记录；B2-F003 顺手记录）
- 预审自检（测试契约 slice）— 2 个 slice（ORC-NODE-01 + ORC-NODE-02）
- **语义回归自检**（B2-F001 semantic_risk=true，两条 ORC 实测输出粘贴）
- **Fix Card**（B2-F001 完整填写，见 §1.2；B2-F003 无需 Fix Card 因属 LOW design-concern 顺手）
- 验证清单自检（§1.8 全部 7 项证据粘贴）
- 根因分析（B2-F001 必填：症状/根因/证据/影响面/排除假设）
- 自查（边界 case / 状态变量 / 字符串匹配 三要素 + 实测输出）

### 1.10 R3 审查范围（给 Reviewer 的预告）

按 review-templates.md FAIL 升级规则："Round 3 仅审 code-bug 和 test-gap"：
- R3 审查只审 B2-F001（code-bug）的修复
- B2-F003 已由 Planner 决定顺手收窄，R3 审查可复核 "hot-reload" grep 零残留
- B2-F002 verified 不重审

PASS 条件：
- B2-F001 EBADENGINE 零警告在 clean env 下复现成立
- 未引入新 HIGH/MED code-bug 或 test-gap
- Vitest 24/24 PASS 不退化

### 1.11 L017 行为变更审批（已完成）

- B2-F001 方案 A（Node floor >=22.12.0）是 behavior_change（改基线环境要求）
- 用户 2026-04-14 Planner 会话中已 **approved**（"同意推荐" = approve A + X）
- R3 审查交接单「行为变更审批记录」段必须记录：
  ```
  | Finding | 行为变更摘要 | 用户决定 | 理由 |
  |---------|-------------|---------|------|
  | B2-F001 方案 A | 升级 Node floor 到 >=22.12.0（package.json engines + .nvmrc）| approved @2026-04-14 Planner | 用户批准 "推荐 A + X"。与 lockfile 锁定 dep 匹配，自然消除 EBADENGINE；回避方案 B 降级 dep 带来的退化风险 |
  ```

---

## §2 启动 Prompt（复制到新窗口）

```
[edu-cloud] Executor (Phase 1 Batch 2 Gate 2 R3 修复) | 2026-04-14 08:10:39
项目: C:\Users\Administrator\edu-cloud

声明：[T4] haofenshu Phase 1 Batch 2 Gate 2 Code Review Round 3 — 修复 B2-F001 Node floor 升级（方案 A，user approved） + B2-F003 顺手 handoff 措辞清理（方案 X）

读取 R3 交接卡（本窗口入口）: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-14-haofenshu-phase1-batch2-r3-handoff.md
读取 R2 authoritative FAIL 报告: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-phase1-review-report-batch2-r2.md
读取 R2 Executor 自审: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-phase1-review-handoff-batch2-r2.md
读取 B2-F002 独立修复设计（护航，不碰）: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-14-auth-fail-closed-repair-design.md
读取 Plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-phase1-plan.md
读取 Design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-biz-replication-design.md

角色: Executor（不是 Planner、不是 Reviewer）。使用 executing-plans skill。

R3 修复范围（严格）:
1. B2-F001: 升级 Node floor 到 >=22.12.0（engines + .nvmrc），消除 npm ci EBADENGINE 警告
2. B2-F003 顺手: 删除 R2 handoff line 171 的 "WSL 后端 hot-reload 失效" 旧措辞引用

不做:
- ❌ 降级 dep 版本
- ❌ 改 AuthError / useMenus / default.vue / auth.ts 任何逻辑
- ❌ 启动 Batch 3

环境预检（第一件事）:
   node --version
   若非 22.12+ → 切换 nvm install 22.12.0 && nvm use 22.12.0 后再继续
   若无法切换 → 停止并向 Planner 报告

scope: 严格在 frontend-nuxt/{package.json,.nvmrc,.npmrc,package-lock.json} + 可选根 .nvmrc + CLAUDE.md 进度行 + docs/plans/2026-04-12-...-handoff-batch2-r2.md（B2-F003 顺手） + docs/plans/2026-04-14-...-review-handoff-batch2-r3.md（R3 审查交接单新建）。禁止触碰 frontend/ / src/edu_cloud/ / alembic/ / frontend-nuxt/composables|layouts|stores|tests/。

验证 7 项断言（全部必须通过）:
1. node --version ≥ v22.12.0
2. cd frontend-nuxt && rm -rf node_modules && npm ci --ignore-scripts 2>&1 | tee /tmp/npm-ci-r3.log
3. grep -c EBADENGINE /tmp/npm-ci-r3.log → 0
4. npm ls @nuxt/kit @nuxt/schema commander crossws --depth=2 2>&1 | grep -cE "invalid|extraneous" → 0
5. npx nuxt prepare → exit 0
6. ./node_modules/.bin/vitest.cmd run → 24/24 PASS
7. grep -c "hot-reload" docs/plans/2026-04-12-haofenshu-phase1-review-handoff-batch2-r2.md → 0

产出 R3 审查交接单: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-14-haofenshu-phase1-review-handoff-batch2-r3.md
必填段落: 逐 Task 自审 / 预审自检 / 语义回归自检（ORC-NODE-01/02）/ Fix Card (B2-F001) / 验证清单自检（7 项证据）/ 根因分析 / 自查 / 行为变更审批记录（记录用户 2026-04-14 approved 方案 A）

完成后输出审查交接单。
```

---

## §3 Planner 留给自己 / 下一任 Planner 的备忘

- R3 交接单产出 + commit 后，Planner 调 codex-review (code) Gate 2 R3 审查 → 写回 `gates.json.code_review_batch2` (status=pass + report_path 指向 R3 PASS 报告，不得保留 R2 FAIL 路径)
- R3 审查范围 per review-templates.md: 仅审 code-bug 和 test-gap（B2-F001 修复 + B2-F003 顺手复核）
- 若 R3 PASS → 更新 CLAUDE.md「进行中设计」段相关条目 → 评估 Batch 3 启动（plan Task 10-12：usePowerOptions + PowerFilter + 45 页面 stub + 端到端验证）
- 若 R3 再 FAIL → R2-R3 已用完 2 轮配额，按 review-templates.md 升级处置：code-bug 必须修复（可能要 R4 但已超配），design-concern 记入 design.md §待处置
- **平行轨道未动**（延续 status-snapshot §6）：
  - 5 → **2 稳定 failures** 定性（`test_tool_access_fail_closed.py::{test_no_capability_record_rejects, test_partial_capability_match_rejects}`）
  - conduct-module Gate 1 plan_review=skipped 追认
  - CLAUDE.md drift T1 维护（19→20 模块 / 1976→1983 tests / menu 补写）
  - phase1b/c/d/2.1/2.2 state.json 陈旧清理
  - R2-NEW-02 deferred 2026-05-15（module-governance 优化）
  - 18 模块 MODULE.md 自愈式债务
  - 2 个 .conduct-fix-intent-* 隐藏文件归档
- **conduct-roadmap [批次 1 draft]**（CLAUDE.md「进行中设计」新加的 topic）：本 Planner 轨道未涉，等 haofenshu Batch 2 PASS 后可评估是否串行还是并行推进
