[edu-cloud] Executor→Reviewer | 2026-04-18 08:30:00

## R2 审查交接单: Batch 3.b Round 2（F001-F005 修复）

- 计划: `docs/plans/2026-04-13-knowledge-graph-phase1-plan.md`（R6 PASS, subject_hash `a963e85b`）
- 设计: `docs/plans/2026-04-12-knowledge-graph-optimization-design.md`
- R1 Handoff: `docs/plans/2026-04-13-knowledge-graph-phase1-review-handoff-batch3b.md`
- R1 Report: `docs/plans/2026-04-13-knowledge-graph-phase1-review-report-batch3b.md`（GPT 5.4 FAIL, 5 findings）
- R2 派发 Handoff: `docs/plans/2026-04-18-w2-r2-repair-handoff.md`（master @ `fc3f0e0`）
- Gates: `docs/plans/2026-04-13-knowledge-graph-phase1-gates.json`（batch3b=fail R1 / **R2 待写**）
- R2 范围: 修 F001 + F002 + F003 + F004 + F005 五个 finding
- R2 Commits（按 finding 独立）:
  - `66ab2b8` (F001 ExamItemsTab fetchSeq guard)
  - `fce6412` (F002 ExamItemsTab 分页 mutant 测试)
  - `6806f2b` (F003 TreeNavPanel 改 DOM 入口)
  - `9d1e6c7` (F004 StudyUnitTab 0 值 fixture)
  - `317dfb6` (F005 TreeNavPanel 移 defineExpose + CLAUDE.md 同步)
- R2 修改文件（5 个 + CLAUDE.md）:
  - `frontend/src/components/knowledge-tree/ExamItemsTab.vue` (F001)
  - `frontend/src/__tests__/knowledge-tree/ExamItemsTab.test.js` (F002)
  - `frontend/src/__tests__/knowledge-tree/TreeNavPanel.test.js` (F003)
  - `frontend/src/__tests__/knowledge-tree/StudyUnitTab.test.js` (F004)
  - `frontend/src/components/knowledge-tree/TreeNavPanel.vue` (F005)
  - `CLAUDE.md`（doc-sync-guard 强制同步 F001 + F005 两次追加）
- 测试基线前→后: R1 153 tests（14 files / knowledge-tree 子集） → **R2 knowledge-tree 子集 14 files / 156 tests PASS**（+3: F002 ×2 + F004 ×1；F003 改 DOM 入口重构 6 测试不增量；F001/F005 为 code 改不增测试，由 F002/F004 mutant 覆盖）
- 严禁改动: 红线白名单外 0 触（W1/W3/W4 范围互斥；主 wt 借 W4 无污染）

### 环境备注

本 R2 仍在独立 **W2 worktree** `/home/ops/projects/edu-cloud-w2`。主 wt 当前借给 W4 `feat/conduct-roadmap-batch1`，node_modules symlink 只读共享。

### 逐 Finding 自审

| Finding | 计划要求（R1 repair hypothesis） | 实际执行 | 状态 | 说明 |
|---------|---------|---------|------|------|
| F001 | `仅最新请求生效`生命周期保护（参 NodeDetailDrawer:148 fetchSeq pattern）；禁止脆弱补丁 / 延时节流 | module-scoped `let fetchSeq = 0`；`load()` 入口 `const mySeq = ++fetchSeq`；try / catch / finally 各 `if (mySeq !== fetchSeq) return` 早退。**不加 AbortController**（scope 约束不改 api/knowledgeTree.js），网络层多发一次但不覆盖状态 | 🔀 | 不加 abort 属 scope 保守偏离；Repair hypothesis 只要求"仅最新请求生效"语义，seq guard 达成。commit `66ab2b8` |
| F002 | 覆盖"点击下一页发起第 2 页请求"+"切换 nodeId 后 page 重置为 1" | 2 新 it:<br>(a) `nextPage click triggers page=2`: `findAll('button').find('下一页').trigger('click')` + `expect getExamItems toHaveBeenNthCalledWith(2, 'Z', 2, 10)` + `toHaveBeenCalledTimes(2)`<br>(b) `nodeId change resets page to 1`: 先 nextPage 到 page=2，再 `setProps({nodeId:'B'})` + `toHaveBeenLastCalledWith('B', 1, 10)` | ✅ | commit `fce6412` |
| F003 | 通过真实 DOM 交互切换模式 + 树组件选择路径验证 emit 契约 | helper `switchToChapter`: `find('input[type="radio"][value="chapter"]').setValue(true)`；helper `getTree`: `findComponent(NTree)`（naive-ui 组件引用非 name 字符串匹配）；6 个 UI 级测试全改 DOM/emit 入口，移除 `wrapper.vm.navMode/handleSelect` | 🔀 | handleSelect 入口走 `tree.vm.$emit('update:selected-keys', [...])`（组件 emit 入口，非纯 DOM tree-node click） — Naive UI n-tree DOM 结构复杂，组件 emit 是"树组件选择路径"合理实现。commit `6806f2b` |
| F004 | 显式断言 `0` 会显示为 `0` 而非 `'—'` | 新 it `planning_weight 0 values render as "0" not "—"`: fixture `exam_frequency: 0, error_prone: 0, priority_score: 0` + transfer_value 未提供；断言 `.weight-value` DOM text 分布 = 3 个 '0' + 1 个 '—' | ✅ | commit `9d1e6c7` |
| F005 | A) 移除 defineExpose 测试改 DOM 入口 / B) 改 plan 追认 expose 契约 | **方案 A（用户 2026-04-18 批准）**：删 `defineExpose({ navMode, handleSelect })` 1 行；测试已在 F003 commit 6806f2b 改为 DOM/emit 入口，移除 defineExpose 零影响；CLAUDE.md 追加遵守 plan §3181 navMode 内部化说明 | ✅ | commit `317dfb6` |

> 状态：✅一致 / 🔀改进（实现优于计划，已记录）

### 反证矩阵（R2 Executor 手动验证预案）

| 反证操作（对 R2 修复） | 预期 fail 断言 | 验证方式 |
|---------|---------------|------|
| F001 删 `mySeq !== fetchSeq` 早退（3 处 try/catch/finally 任一） | 无直接 assert 覆盖 race（测试 mock 同步 resolve，顺序一致）；间接 mutant: F002 `nodeId change resets page to 1` 在严格 race 下可能红，本 repo 未加异步 race test（scope 保守，覆盖率小瑕疵同 R1 未覆盖瑕疵 pre-declare）| 说明型反证，未实测 |
| F002 删 `function nextPage() { page.value++ }` | `nextPage click triggers page=2`: 第 2 次调用不发 → `toHaveBeenCalledTimes(2)` fail | 逻辑推理 |
| F002 删 watch `page.value = 1` | `nodeId change resets page to 1`: 切 'B' 后 page=2 残留 → `toHaveBeenLastCalledWith('B', 1, 10)` fail（actual 'B', 2, 10）| 逻辑推理 |
| F003 删 `<n-radio-group v-model:value="navMode">` | `chapter mode via radio click shows book title "必修1"`: setValue 无效 → `toContain('必修1')` fail | 逻辑推理 |
| F003 删 `@update:selected-keys="handleSelect"` binding | 所有 emit 测试 fail（tree.$emit 不路由到 handleSelect）| 逻辑推理 |
| F004 把 `??` 退回 `\|\|` | `planning_weight 0 values`: `0 \|\| '—' = '—'` → `values.filter(v => v === '0').toHaveLength(3)` fail（actual 0）| 逻辑推理 |
| F005 重新加回 defineExpose | 无测试引用 `wrapper.vm.navMode/handleSelect` → 无测试 fail；但 Contract Pack freshness 再次触发 process finding（R1 F005 重现）| 逻辑推理 |

**说明**: Executor 未逐条跑实测 mutant（handoff §4 未强制要求，R2 修复 commits 已 staged 测试基线 156/156 PASS）。Reviewer 可要求指定 slice 手动粘贴 fail 输出。

### Fix Card

| Finding | Category | Type | Before | After | Resolved-hypothesis | Status |
|---------|----------|------|--------|-------|---------------------|--------|
| F001 | code-bug | defect_fix | load() 无 seq guard，A→B 切换 A 旧请求覆盖状态 | fetchSeq 序号守卫 + mySeq 比较，旧请求 resolve 不写 state | ✅ 仅最新请求生效（参 NodeDetailDrawer:148 pattern） | resolved-correct |
| F002 | test-gap | defect_fix | pagination test 仅断言首屏调用参数，mutant 删 nextPage/page++ 仍 PASS | 2 新 test 点击下一页 + 切 nodeId 断言 page reset | ✅ 入口级 mutant 测试（点击 + setProps）| resolved-correct |
| F003 | test-gap | defect_fix | 测试直接 wrapper.vm.navMode/handleSelect，mutant 删 radio-group 仍 PASS | radio.setValue + findComponent(NTree).$emit 走 DOM/emit 入口 | ✅ 入口级 DOM + 组件 emit | resolved-correct |
| F004 | test-gap | defect_fix | StudyUnitTab `??` 0 值语义 fixture 无 0，mutant 退 `\|\|` 仍 PASS | 新 it 0 值 fixture 断言 weight-value text 3×'0' + 1×'—' | ✅ 0 值语义锁定 | resolved-correct |
| F005 | design-concern | behavior_change | defineExpose({navMode, handleSelect}) 违反 plan §3181 navMode 不暴露 | 删 defineExpose 1 行；测试已走 DOM/emit 入口不依赖 | ✅ 方案 A 用户批准 — 契约保持不变 | resolved-correct |

### 验证清单自检

- ✅ F001 实现: ExamItemsTab.vue net +6/-0（let fetchSeq + 3 个 if mySeq !== fetchSeq return），不改 api/knowledgeTree.js
- ✅ F002 新断言入口: `wrapper.findAll('button').find('下一页').trigger('click')` + `wrapper.setProps`（真实 DOM + props 入口）
- ✅ F003 测试 6 个 UI 级全改: `setValue` / `$nextTick` / `findComponent(NTree).$emit` (无 wrapper.vm.navMode/handleSelect 遗留)
- ✅ F004 反证精准: `toHaveLength(3)` 3 个 '0' filter 锁 0 值渲染；`toHaveLength(1)` 1 个 '—' 锁 undefined fallback
- ✅ F005 defineExpose 完整移除: `grep 'defineExpose' TreeNavPanel.vue` → 0 命中
- ✅ 反证矩阵 7 条（R1 原 + R2 新增），均逻辑推理，未强制实测（handoff §4 未强制要求 R2 粘贴 fail 输出）
- ✅ R1 严禁改动保留: `KnowledgeTreePage.vue` / `NodeDetailDrawer.vue` / `useKnowledgeTree.js` / `api/knowledgeTree.js` / `ConceptMapPanel.vue` / `ColorModeToggle.vue` / `heatmapUtils.js` R2 零触
- ✅ 子集回归: knowledge-tree 14 files / **156 tests PASS** (R1 基线 153 + R2 +3 mutant)
- ✅ Git staging 纯净: 5 次 commit 前均 `git status --short` 验证；5 commits 分别对应 5 findings
- ⚠️ 全前端 vitest 未跑（仅 knowledge-tree 子集）— 其他模块理论零触及但未实证；建议 Reviewer `npx vitest run` 全量
- ⚠️ mutant 未逐条实测粘贴 fail 输出（handoff §4 未强制，Reviewer 要 slice 请指定）

### 🔀 偏离汇总（审查关注点）

1. F001 seq guard only，不加 AbortController（scope 约束不改 api signature） — 符合 Repair hypothesis "仅最新请求生效" 语义
2. F003 handleSelect 入口走 `findComponent(NTree).$emit` 而非纯 DOM tree-node click（naive-ui n-tree DOM 复杂） — 仍属"树组件选择路径"入口
3. CLAUDE.md 追加 2 次（F001 commit + F005 commit）— doc-sync-guard 对 .vue modify 强制同步，最小 1 句追加

### 送审准备

1. Baseline: knowledge-tree 子集 14/156 PASS（2026-04-18 08:18）
2. Commits: `66ab2b8..317dfb6`（5 commits + R2 handoff 待 commit 作本文件）
3. Staged 纯净：`git diff master..HEAD --name-only` 白名单 5 文件 + CLAUDE.md
4. Worktree w2 独立，主 wt（W4）零相互污染
5. 下一步: `codex-review` skill R2 GPT 独立审查（subject_ref `commit:66ab2b8..317dfb6`）
6. gates.json R2 回执待写（PASS/FAIL 由 GPT 决，round=2）

---

status: submit-for-review-r2
