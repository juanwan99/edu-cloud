---
type: handoff
created: 2026-04-14 06:16:17
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-biz-replication-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-phase1-plan.md
independent_fix_design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-14-auth-fail-closed-repair-design.md
r1_report: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-phase1-review-report-batch2.md
r1_handoff: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-phase1-review-handoff-batch2.md
---

## 任务背景（新窗口零上下文假设）

### 这是什么
`edu-cloud` 好分数业务复刻 Phase 1 / Batch 2 (Frontend 骨架) / **Gate 2 Code Review R1 FAIL → R2 修复**。

### 当前阶段
**Batch 2 代码已落盘 (commits `08d86f0..674cd99`)，R1 审查 FAIL，进入 R2 修复。**

### R1 FAIL 原因（3 个 finding 全部为 defect_fix）

| ID | Severity | Category | Type | 结论 |
|----|----------|----------|------|------|
| **B2-F001** | MED | code-bug | defect_fix | frontend-nuxt 依赖锁文件不可复现（`npm ci --ignore-scripts` 失败 + `npm ls` 报 invalid） |
| **B2-F002** | MED | code-bug | defect_fix | `useMenus.ts` 吞错破坏 plan Task 8 fail-closed 契约（触及 fallback strategy + lifecycle，已出独立修复设计） |
| **B2-F003** | LOW | design-concern | defect_fix | 交接单 Step 3/4 阻塞归因不准（不阻塞 Gate，随 R2 交接单一并修正措辞） |

### R1 报告独立验证结论

- Vitest 反证 2 条 anti-tautology 成立（applyLoginResponse + getPowerOptions）
- Gate Step ① Nuxt dev ✅ + Step ② login ✅（admin + t_yw_001）
- Gate Step ③④ 建议 **deferred**（非 FAIL，也非 PASS —— 9000 陈旧进程缺 `/api/v1/menus`，fresh 9001 正常）
- plan risk_modules 应补入 `frontend-nuxt/package.json` + `package-lock.json`（R2 追认）

## 约束与偏好（design 未记录的增量）

- **任务级别**: T4（Batch 2 R2 修复属 Phase 1 Batch 2 范围内，不升级 T）
- **角色**: Executor（执行修复），不是 Planner、不是 Reviewer
- **流程**: Round 2 修复所有 finding → R2 审查交接单 → Planner 调度 codex-review R2
- **B2-F002 修复铁律（红旗模式独立设计）**:
  - 必须按 `docs/plans/2026-04-14-auth-fail-closed-repair-design.md` §2 实施（新增 `AuthError` sentinel + 职责分层）
  - 禁止修复模式（独立设计 §0 non-goals + repair_hypothesis 红旗）：
    * ❌ 在 `useMenus.ts` 直接删 try/catch
    * ❌ 在 `default.vue` 外层加菜单空值检查触发 logout
    * ❌ 把"菜单降级"与"auth fail-closed"合并为同一策略
  - Fix Intent Card（§3）protected invariants：
    * ORC-auth-fail-closed（plan Task 8 契约）
    * ORC-menu-degrade（非 auth 错误不踢 session）
    * ORC-auth-state-consistency（logout 清空 token/user/menus）
    * ORC-no-double-logout（单次 401 最多一次 logout）
- **B2-F001 修复铁律**:
  - 必须 `rm -rf node_modules package-lock.json && npm install`（**不要用 `--legacy-peer-deps`**）
  - `npm ci --ignore-scripts` 必须零报错
  - `npm ls @nuxt/kit @nuxt/schema commander crossws --depth=2` 必须零 invalid
  - 若 peer 冲突 → 调整 package.json 版本，不回退 `--legacy-peer-deps`
- **B2-F003 修复**:
  - R2 交接单措辞收窄为"9000 常驻后端进程陈旧/未重启阻塞（独立复现：fresh 9001 对照实例正常）"
  - 不单独 commit，随 R2 交接单一并
- **Commits 策略**:
  - 建议单个 commit 合并 B2-F001 + B2-F002 + B2-F003
  - commit message 遵循 R1 修复模式：`fix(frontend,deps): haofenshu phase1 batch2 R2 — B2-F001 lockfile + B2-F002 auth fail-closed + B2-F003 措辞收窄`
- **Windows 环境铁律**: 用 `python` 不用 `python3`；`cd` 用 Bash 工具；服务启动通过 `~/.claude/scripts/serve.py`
- **scope_guard 注意**: R2 修复允许触碰 `frontend-nuxt/` + `docs/plans/2026-04-12-haofenshu-phase1-*` 范围，不要触碰其他未提交工作残留
- **验证铁律**:
  - 本地 Vitest 16/16 PASS（原 12 + 新增 4）
  - 3 条反证验证（独立设计 §3 verification）
  - R2 交接单预审自检表填写 AuthError 3 个 slice + default.vue layout 测试 1 个 slice

## 启动 Prompt（复制到新窗口）

```
[edu-cloud] Executor (Phase 1 Batch 2 Gate 2 R2 修复) | 2026-04-14 06:16:17
项目: C:\Users\Administrator\edu-cloud

声明：[T4] haofenshu Phase 1 Batch 2 Gate 2 Code Review Round 2 — 修复 B2-F001/F002/F003

读取交接卡: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-14-haofenshu-phase1-batch2-r2-executor-handoff.md
读取独立修复设计: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-14-auth-fail-closed-repair-design.md（B2-F002 必须严格按此实施）
读取 R1 审查报告: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-phase1-review-report-batch2.md
读取 R1 交接单: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-phase1-review-handoff-batch2.md
读取 Plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-phase1-plan.md
读取 Design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-biz-replication-design.md

任务（按顺序执行）：

## Step 1: B2-F001 lockfile 对齐（依赖管理）

1.1 `cd C:/Users/Administrator/edu-cloud/frontend-nuxt`
1.2 `rm -rf node_modules package-lock.json`
1.3 `npm install`（**禁止 --legacy-peer-deps**；若 peer 冲突就调整 package.json 版本）
1.4 验证 clean install:
    - `npm ci --ignore-scripts`  期望 exit 0 零报错
    - `npm ls @nuxt/kit @nuxt/schema commander crossws --depth=2`  期望零 invalid
1.5 `./node_modules/.bin/vitest run`  期望原 12 tests 全绿

## Step 2: B2-F002 AuthError 职责分层（严格按独立修复设计 §2）

2.1 `composables/useApi.ts` 新增 `export class AuthError extends Error`，`getMenus` 对 401/403 抛 AuthError（§2.2）
2.2 `composables/useMenus.ts` 导入 AuthError，区分 AuthError（向上抛）vs 其他错误（降级空菜单）（§2.3）
2.3 `layouts/default.vue` catch 分支区分 AuthError（触发 logout）vs 其他（console.warn 保留 session）（§2.4）
2.4 新建 `tests/composables/useMenus.test.ts`（3 测试，§2.5 + §4 Slice 2/3 + Slice 1）
2.5 新建 `tests/layouts/default.test.ts` 或 `tests/integration/auth-lifecycle.test.ts`（1 测试，§4 Slice 4）
2.6 验证 Vitest 16/16 PASS

## Step 3: 反证验证（独立修复设计 §3 verification 反证 1/2/3）

3.1 反证 1: 临时删 useMenus 的 `if (err instanceof AuthError) { throw err }` → 期望 "AuthError 向上抛" 测试 fail → 恢复
3.2 反证 2: 临时把 default.vue 的 `if (err instanceof AuthError)` 改成 `if (true)` → 期望降级集成测试 fail → 恢复
3.3 反证 3: 临时把 useApi.getMenus 的 401 处理改成 `throw err`（不转 AuthError）→ 期望 "getMenus 401 转 AuthError" 测试 fail → 恢复

## Step 4: 独立验证 Pre-existing 继承（R2-F001 延续）

4.1 `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_tool_access_fail_closed.py --tb=line`
    期望: `2 failed, 5 passed`（test_no_capability_record_rejects + test_partial_capability_match_rejects 稳定复现）

## Step 5: B2-F003 + R2 交接单

5.1 写 R2 审查交接单 `docs/plans/2026-04-12-haofenshu-phase1-review-handoff-batch2-r2.md`
    按 ~/.claude/rules-t3/review-templates.md「审查交接单」格式，必填：
    - 逐 Task 自审表（T4-T9 R2 差异列）
    - R1 finding 处置总结表（B2-F001/F002/F003 R2 终态）
    - 预审自检（§4 Slice 1-4 实测证据 + 反证 §3 verification 反证 1-3）
    - 验证清单自检（Step 1-4 每步证据）
    - Pre-existing 2 failures 独立复现证据
    - 行为变更审批记录（B2-F002 Type=defect_fix 保留，非 behavior_change，说明红旗模式已由独立设计 + Fix Intent Card 护航）
    - B2-F003 措辞收窄说明（合并进本交接单）
5.2 commit 落盘：
    ```
    git add frontend-nuxt/ docs/plans/2026-04-12-haofenshu-phase1-review-handoff-batch2-r2.md
    git commit -m "fix(frontend,deps): haofenshu phase1 batch2 R2 — B2-F001/F002/F003

    B2-F001 (MED code-bug, resolved-correct): frontend-nuxt 依赖锁对齐
      rm -rf node_modules package-lock.json && npm install (无 --legacy-peer-deps)
      npm ci --ignore-scripts 零报错; npm ls 零 invalid

    B2-F002 (MED code-bug, resolved-correct): AuthError 职责分层
      useApi.ts 新增 AuthError sentinel + getMenus 401/403 转抛
      useMenus.ts AuthError 向上抛, 其他错误降级空菜单
      default.vue catch 分支区分 AuthError (logout) vs 其他 (保留 session)
      按 2026-04-14-auth-fail-closed-repair-design.md §2 实施
      Fix Intent Card + 4 ORC 保护

    B2-F003 (LOW design-concern, resolved-correct): R2 交接单措辞收窄
      Step 3/4 归因改为 '9000 常驻后端进程陈旧' (fresh 9001 对照正常)

    Test: Vitest 16/16 PASS (原 12 + 新 4), 反证 3 条独立验证通过
    Pre-existing: test_tool_access_fail_closed 2 failed 稳定复现
    "
    ```

## Step 6: 交回 Planner

输出完整 R2 审查交接单（持久化 + commit），请 Planner 新窗口调度 codex-review R2 审查。

---

Windows 环境铁律: 用 `python` 不用 `python3`。
L017 意图守卫: B2-F002 Type=defect_fix 已由独立设计 + Fix Intent Card 明确护航，非 behavior_change，不触发逐条批准流程。
PASS 报告锚定: Gate 2 R2 若 PASS, gates.json report_path 必须指向 R2 报告（不得保留 R1 FAIL 报告）。

完成后输出审查交接单。
```

## 验证清单（本交接卡自检）

- ✅ plan 文件绝对路径存在
- ✅ design 文件绝对路径存在
- ✅ R1 报告绝对路径存在
- ✅ R1 交接单绝对路径存在
- ✅ 独立修复设计绝对路径存在
- ✅ 启动 Prompt 无 `<...>` 占位符、无 "as discussed" 类悬挂引用
- ✅ 启动 Prompt 末尾含 `完成后输出审查交接单。`（T4 格式）
- ✅ 任务级别 T4 已声明
- ✅ B2-F001/F002/F003 修复指令清晰（3 者皆有具体步骤 + 验收标准）
- ✅ B2-F002 红旗模式护航明确（独立设计 + Fix Intent Card + 3 条反证）
- ✅ 禁止修复模式明确列出（独立设计 §0 + 本交接卡约束段）
- ✅ 验证命令完整（Step 1-4 + 反证 3 条）
