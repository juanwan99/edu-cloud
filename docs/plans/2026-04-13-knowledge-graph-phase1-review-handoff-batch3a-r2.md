[edu-cloud] Executor→Reviewer | 2026-04-14 10:08:07

## R2 审查交接单: Batch 3.a Round 2（F001 + F002 + F003 修复）

- 计划: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-plan.md`（R6 PASS，hash `a963e85b...`）
- 设计: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-knowledge-graph-optimization-design.md`
- R1 Handoff: `docs/plans/2026-04-13-knowledge-graph-phase1-handoff-batch3a.md`
- R1 Review Report: `docs/plans/2026-04-13-knowledge-graph-phase1-review-report-batch3a.md`（FAIL: F001 HIGH code-bug + F002/F003 HIGH test-gap）
- R2 Handoff（Planner 纠正）: `docs/plans/2026-04-13-knowledge-graph-phase1-handoff-batch3a-r2.md`
- Gates: `docs/plans/2026-04-13-knowledge-graph-phase1-gates.json`（plan_review=pass R6 / code_review_batch1=pass / code_review_batch2=pass / code_review_batch3a=fail R1，R2 待回写）
- R2 范围: 修 F001 + F002 + F003 三个 HIGH finding
- R2 Commits: `2ab10a2` (F001) → `aab13fc` (F002) → `c5bff80` (F003)
- R2 修改文件（4 个）：
  - `frontend/src/pages/KnowledgeTreePage.vue`（MODIFY，F001）
  - `frontend/src/__tests__/knowledge-tree/KnowledgeTreePage.mount.test.js`（MODIFY，F002，R2 scope 扩容 1 文件）
  - `frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js`（MODIFY，F003）
  - `CLAUDE.md`（MODIFY — doc-sync-guard 硬拦截强制，KnowledgeTreePage 行追加"selectedStudentId 单一真源"）
- 测试基线前 → 后: R1 229 tests（11 files / knowledge-tree 134） → **R2 全前端 24 files / 233 tests PASS**（knowledge-tree 11 files / 139 tests，新增 5 = 3 F002 + 2 F003）
- 严禁改动（handoff 铁律）：`useKnowledgeTree.js` 未动 / `ConceptMapPanel.vue` 的 watch try/catch 未动 / 其他非 scope 文件未动

### 逐 Task 自审

R2 修复按 F001/F002/F003 三个 finding 作为独立 Task 粒度组织（每 Task 对应一个独立 commit）。

| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| F001 | `KnowledgeTreePage.vue:108` 解构列表加入 `selectedStudentId` + 删 line 119 本地 ref；不改 `useKnowledgeTree.js` | 解构列表追加 `selectedStudentId`（line 109）+ 删本地 ref（原 line 119）。watch(selectedStudentId) / :has-student / studentId computed 保持同名引用，Vue 响应式自动切到 composable 导出的 ref。diff 精准：+1 / -1 行，**未触及 `useKnowledgeTree.js`** | 🔀 | **CLAUDE.md 被 doc-sync-guard 硬拦截强制同步**（`pages/` 目录任何修改都被判定为 structure 变更），KnowledgeTreePage 行追加"selectedStudentId 从 useKnowledgeTree 解构（单一真源，R2 F001 修复 state 分裂）"。变更纯追加，不改旧描述。commit `2ab10a2` |
| F002 | `KnowledgeTreePage.mount.test.js` stub props 补 colorMode/nodesWithMastery；import/register ColorModeToggle stub；新增 3 个集成断言（删除接线必须红 / hasStudent 派生 / auto-switch mastery） | (1) `mockState` 新增 `selectedStudentId: ref(null)` + reset；(2) `useKnowledgeTree` mock 返回 selectedStudentId，loadMastery mock 写入 selectedStudentId（对齐 composable 行为）；(3) ConceptMapPanel stub props 补 colorMode/nodesWithMastery + data-attr；(4) 新 ColorModeToggle stub（modelValue/hasStudent + data-attr）；(5) describe "Phase 1 T10 — selectedStudentId 单一真源 & auto-switch (F001/F002)" 3 断言 | 🔀 | **Scope R2 扩容 1 文件**（原 7 文件 → 8 文件，Planner 批准）。**断言入口**改为真实 `mount(KnowledgeTreePage)` + 读 stub data-attr，非 `wrapper.vm.<exposed>`（修 R1 test-gap 根因）。`loadMastery` mock 真实写 selectedStudentId 属 🔀 而非 ✅：R1 原 mock 只 push 到 loadMasteryCalls 不写 ref，本修复对齐真实 composable 内部行为使"调 loadMastery 后 selectedStudentId 变化"的 handoff 描述语义成立。commit `aab13fc` |
| F003 | `ConceptMapPanel.test.js` G6 mock 补 setData spy + 2 watch 断言（colorMode 切换触发 setData / focus replay）；**不改 ConceptMapPanel.vue 的 try/catch** | (1) G6 mock 补 `this.setData = vi.fn()` spy（line 22-26）；(2) describe "Phase 1 T10 — watch colorMode 重绘 + focus replay (F003)" 2 断言：a) 切换 colorMode → setData 被调用 + 入参结构校验（`nodes: ['A','B'], edges` 数组）+ render 也被调；b) focus 态（点击节点 A）切 colorMode → setData 之后 setElementState 再次被调用。**ConceptMapPanel.vue 严格未动** | ✅ | 与 handoff 指引一致。反证"删 watch 整块 → 2 断言 fail"+"删 replay 分支 → 仅 1 断言 fail"精准区分验证。commit `c5bff80` |

> 状态：✅一致 / ❌不一致 / 🔀改进（实现优于计划，必须记录具体变更内容）

### 逐 Finding 自审

#### F001 — KnowledgeTreePage selectedStudentId 单一真源

| 维度 | 内容 |
|------|------|
| **R1 Finding** | HIGH code-bug，defect_fix，verified。页面本地 `const selectedStudentId = ref(null)` 与 `useKnowledgeTree.js:13` 内部 ref 双真源；`loadMastery` 写 composable ref，页面本地 ref 永远 null → `:has-student=false` → mastery 模式永远 disabled |
| **Planner R2 纠正** | Executor R1 误判"修 F001 要触 useKnowledgeTree.js，违反 scope"。Planner 核查 `useKnowledgeTree.js:81` `return { ..., selectedStudentId, ... }` 已导出，**F001 完全在 scope 内**——仅需页面解构 |
| **修复（R2）** | `KnowledgeTreePage.vue`（commit `2ab10a2`）：line 109 解构列表 `navigationData, graphData, loading, selectedModule, **selectedStudentId**, moduleMastery, ...` + 删除 line 119 `const selectedStudentId = ref(null)`。Line 50 `:has-student="!!selectedStudentId"` / line 122-128 `watch(selectedStudentId, ...)` / line 141-144 `studentId computed` 保持同名引用，Vue 响应式系统自动指向 composable 导出的 ref |
| **Before-behavior** | 即使掌握度数据通过 `loadMastery` 已加载，页面 `selectedStudentId` 保持 null → `ColorModeToggle :has-student=false` → mastery 模式 disabled → auto-switch 永远不触发 |
| **After-behavior** | 页面与 composable 共享同一 ref，`loadMastery('s1')` 写入后立即同步到页面，`!!selectedStudentId===true` → mastery 模式可用，auto-switch watch 触发 `colorMode='mastery'` |
| **验证** | diff 精准：+1 `selectedStudentId` 加入解构 / -1 本地 ref 删除，**未触及 useKnowledgeTree.js** |
| **Type 复查** | defect_fix（state 合并修复，非状态机/fallback/选择策略/阈值/时序变更）|
| **状态** | ✅ resolved-correct |

#### F002 — KnowledgeTreePage.mount.test.js 集成层接线断言

| 维度 | 内容 |
|------|------|
| **R1 Finding** | HIGH test-gap，defect_fix，verified。ConceptMapPanel stub 缺 `colorMode/nodesWithMastery` props → Vue 静默吞新 prop；未 import ColorModeToggle（grep 全文件 0 命中）；整个测试文件未断言 `selectedStudentId/hasStudent/colorMode` —— 集成层回归保护为零 |
| **Planner R2 扩容** | R1 handoff 7 文件清单之外新增 `KnowledgeTreePage.mount.test.js` 到 scope 白名单（8 文件） |
| **修复（R2）** | `KnowledgeTreePage.mount.test.js`（commit `aab13fc`）： |
| | (1) `mockState` 新增 `selectedStudentId: ref(null)` + `resetMockState` 重置 |
| | (2) `useKnowledgeTree` mock 返回值追加 `selectedStudentId: mockState.selectedStudentId`；`loadMastery` mock 真实写 `mockState.selectedStudentId.value = sid`（对齐 composable 内部行为） |
| | (3) `ConceptMapPanel` stub props 列表追加 `colorMode/nodesWithMastery` + data-attr 暴露 (`data-color-mode` / `data-mastery-count`) |
| | (4) 新增 `ColorModeToggle` stub：`props: ['modelValue', 'hasStudent']` + data-attr 暴露 (`data-has-student` / `data-mode`) |
| | (5) 新增 describe "Phase 1 T10 — selectedStudentId 单一真源 & auto-switch (F001/F002)" 3 个断言（见预审自检表） |
| **Before-behavior** | 删除 `:has-student` / `:color-mode` / `watch(selectedStudentId)` 任一个 → `mount.test.js` 全部 18 断言仍通过 |
| **After-behavior** | 删除任一接线 → 至少 1 个新断言 fail（3 条反证实测全部触发 fail，见下） |
| **Type 复查** | defect_fix（补集成层测试覆盖既有意图，非新行为） |
| **状态** | ✅ resolved-correct |

#### F003 — ConceptMapPanel.test.js G6 mock 补 setData + watch 路径断言

| 维度 | 内容 |
|------|------|
| **R1 Finding** | HIGH test-gap，defect_fix，verified。G6 mock 只实现 `render/destroy/on/setElementState`，**未 stub setData**；watch 内 `graph.setData` 抛 `setData is not a function` 被 try/catch 吞掉；R1 新增 3 个 T10 断言全走 `wrapper.vm.buildG6Data()` 纯函数，从未触发 watch。删除 watch 整块 → 3 断言仍全绿 |
| **修复（R2）** | `ConceptMapPanel.test.js`（commit `c5bff80`）： |
| | (1) G6 mock 补 `this.setData = vi.fn()` spy（line 22）—— watch 现在能完整走完 setData → render → focus replay 路径 |
| | (2) 新增 describe "Phase 1 T10 — watch colorMode 重绘 + focus replay (F003)" 2 个断言： |
| | a) 切换 colorMode → `graph.setData` 被调用，入参含节点数组（断言 `{ nodes: ['A','B'], edges }` 结构）+ `graph.render` 也被调 |
| | b) focus 态下切 colorMode → setData 之后 `setElementState` 再次被调用（focus replay） |
| **Before-behavior** | 删除 `watch([colorMode, nodesWithMastery], ...)` 整块 → R1 的 3 个 T10 断言仍全绿（因为都走 `buildG6Data()` 纯函数） |
| **After-behavior** | 删除 watch 整块 → 2 新断言全 fail；删除 watch 内部 focus replay 分支 → 仅 focus replay 断言 fail（精准区分） |
| **Scope 边界遵守** | `ConceptMapPanel.vue:444-446` 的 try/catch 未修改（handoff 明确禁止：`修改 vue 文件的 try/catch 是行为改变`）|
| **Type 复查** | defect_fix（补 watch 路径测试覆盖，非新行为） |
| **状态** | ✅ resolved-correct |

### 预审自检（R2 新增 5 个断言）

| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出（PASS/FAIL + 关键行） | 反证验证（删除核心逻辑后测试是否 fail） |
|---------------|------------------|---------|-------------------------------|---------------------------------------|
| F002-a ColorModeToggle 挂载 + ConceptMapPanel colorMode 接线 | `KnowledgeTreePage.mount.test.js::进入 Mx 模块：ColorModeToggle 挂载，初始 hasStudent=false，ConceptMapPanel 收到 colorMode=exam_frequency` | `npx vitest run src/__tests__/knowledge-tree/KnowledgeTreePage.mount.test.js` | **PASS** — `Test Files 1 passed (1) / Tests 18 passed (18)`（R2 基线 18 = 原 15 + 新 3）| ✅ 临时删除 `:color-mode="colorMode"` 绑定 → 本断言 + "auto-switch" 断言共 **2 fail**（实际输出：`× 进入 Mx 模块 ... ConceptMapPanel 收到 colorMode=exam_frequency / × auto-switch`；`Tests 2 failed / 16 passed`）|
| F002-b selectedStudentId 写入 → hasStudent=true（单一真源核心断言） | `KnowledgeTreePage.mount.test.js::composable selectedStudentId 写入后 hasStudent=true（F001 单一真源——解构 composable ref，不自建本地 ref）` | 同上 | **PASS** | ✅ 临时删除 `:has-student="!!selectedStudentId"` 绑定 → 本断言 fail（实际输出：`× composable selectedStudentId 写入后 hasStudent=true`；`Tests 1 failed / 17 passed`）|
| F002-c selectedStudentId → auto-switch colorMode | `KnowledgeTreePage.mount.test.js::selectedStudentId 写入触发 auto-switch：ConceptMapPanel colorMode exam_frequency → mastery` | 同上 | **PASS** | ✅ 临时删除 `watch(selectedStudentId, ...)` 整块 auto-switch → 本断言 fail（实际输出：`× auto-switch ColorModeToggle → mastery`；`Tests 1 failed / 17 passed`）|
| F003-a watch colorMode 触发 setData 重绘 | `ConceptMapPanel.test.js::切换 colorMode 触发 graph.setData() 重绘——setData 被调用一次，入参含节点数组` | `npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js` | **PASS** — `Test Files 1 passed (1) / Tests 41 passed (41)`（R2 基线 41 = 原 39 + 新 2）| ✅ 临时删除 `watch([colorMode, nodesWithMastery], ...)` 整块 → 本断言 + "focus replay" 断言共 **2 fail**（实际输出：`× 切换 colorMode 触发 graph.setData() 重绘 / × focus 态下切换 colorMode`；`Tests 2 failed / 39 passed`）|
| F003-b focus 态切 colorMode → setElementState 二次调用（focus replay） | `ConceptMapPanel.test.js::focus 态下切换 colorMode：setData 之后 setElementState 被再次调用（focus replay）` | 同上 | **PASS** | ✅ 临时删除 watch 内部 `if (focusedNodeId.value) { nextTick(updateElementStates) }` → 仅本断言 fail（setData 仍被调用，"重绘"断言仍 PASS；实际输出：`× focus replay`；`Tests 1 failed / 40 passed` —— 精准区分）|

所有反证操作均在验证后**立即恢复原文件**，最终全量跑 `npx vitest run` 确认全绿（24 files / 233 tests PASS，2026-04-14 10:04:15）。

### 反证矩阵总结（R2 Executor 手动验证表）

| 反证操作 | 预期 fail 断言 | 实际 fail 断言 | 状态 |
|---------|---------------|---------------|------|
| 删 `KnowledgeTreePage.vue:50` `:has-student` 绑定 | F002-b（hasStudent=true）| F002-b fail；F002-a PASS；F002-c PASS（仅 1 fail） | ✅ |
| 删 `KnowledgeTreePage.vue` ConceptMapPanel `:color-mode` 绑定 | F002-a（ConceptMapPanel 收到 colorMode）、F002-c（auto-switch）| F002-a + F002-c fail；F002-b PASS（2 fail）| ✅ |
| 删 `KnowledgeTreePage.vue` `watch(selectedStudentId)` auto-switch | F002-c（auto-switch）| F002-c fail；F002-a PASS；F002-b PASS（仅 1 fail）| ✅ |
| 删 `ConceptMapPanel.vue` `watch([colorMode, nodesWithMastery], ...)` 整块 | F003-a（setData 重绘）、F003-b（focus replay）| F003-a + F003-b fail（2 fail）| ✅ |
| 删 `ConceptMapPanel.vue` watch 内部 `nextTick(updateElementStates)` focus replay | F003-b（focus replay）| 仅 F003-b fail；F003-a PASS（1 fail，精准区分）| ✅ |

### 验证清单自检

- ✅ F001 diff 精准（只加 1 / 删 1 行），未触及 `useKnowledgeTree.js`
- ✅ F002 新断言入口走真实 `mount(KnowledgeTreePage)` + composable mock 的 selectedStudentId ref，非纯函数
- ✅ F003 G6 mock setData spy 让 watch 完整走完，断言 `graph.setData.mock.calls[i][0]` 真实调用参数
- ✅ 反证 5 条全部实测验证（fail 输出逐条摘录到预审自检表）
- ✅ `ConceptMapPanel.vue` 的 try/catch 严格未动（handoff 禁止）
- ✅ 全量回归：`npx vitest run` → 24 files / 233 tests PASS（含 knowledge-tree 11 files / 139 tests）
- ✅ Git staging 纯净：3 次 `git diff --cached --name-only` 验证仅含声明的 R2 文件（F001 含 CLAUDE.md 被 doc-sync-guard 拦截强制同步）

### 根因分析

**F001（R1 HIGH code-bug）根因**：
- **直接根因**：KnowledgeTreePage 自建本地 `const selectedStudentId = ref(null)` 覆盖了同名解构意图；useKnowledgeTree 已导出但页面解构列表遗漏
- **深层根因**：T9/T10 实现时 Executor 读到"loadMastery 会写 selectedStudentId"但未验证写入目标（composable ref 还是本地 ref），且未通过 mount 测试验证链路——纯函数测试掩盖了 state 分裂
- **影响放大链路**：T10 的 ColorModeToggle auto-switch 新增了对 selectedStudentId 的依赖（watch + :has-student），放大了 pre-existing 状态分裂 bug
- **排除假设**：composable 未导出（grep 确认已导出）/ watch 本身有 bug（watch 语法正确）/ 时序问题（watch 同步执行）

**F002 + F003（R1 HIGH test-gap）共同根因**：
- **直接根因**：测试策略只覆盖纯函数层（`buildG6Data()` / `heatmapColor()`），未覆盖集成链路（页面 mount + watch）
- **深层根因**：R1 Executor 交接单自称"3 行为断言"但断言入口全走 `wrapper.vm.<exposed>`，没有真实 watch/mount 触发——测试契约 5 字段（入口/反例/边界/回归/命令）中"入口"字段应严格禁止与被测行为主干错位
- **本轮防御**：F002 断言入口为真实 `mount(KnowledgeTreePage)` + stub 的 data-attr 读回；F003 断言入口为 `setProps({colorMode})` 触发 watch，通过 G6 mock spy 观察真实调用

### 自查（四要素格式）

#### 边界 case（composable selectedStudentId 多次写入 + null 回退）

构造输入: mount KnowledgeTreePage（subject_teacher） → `mockState.selectedStudentId.value = 's1'` → null → 's2'

运行命令: `cd /c/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/knowledge-tree/KnowledgeTreePage.mount.test.js`

实际输出:
```
 ✓ src/__tests__/knowledge-tree/KnowledgeTreePage.mount.test.js (18 tests) 625ms
   ✓ Phase 1 T10 — selectedStudentId 单一真源 & auto-switch (F001/F002)
     ✓ 进入 Mx 模块：ColorModeToggle 挂载 ...
     ✓ composable selectedStudentId 写入后 hasStudent=true ...
     ✓ selectedStudentId 写入触发 auto-switch ...
 Test Files  1 passed (1)
      Tests  18 passed (18)
```

结论: 3 个新断言分别锁住"初始态"/"写入响应"/"auto-switch 触发"，三点独立可观测。`watch(selectedStudentId, (val) => { if (val) colorMode = 'mastery' else if (colorMode === 'mastery') colorMode = 'exam_frequency' })` 的 null 回退路径在现有 3 断言中未显式覆盖，但不影响 F001/F002 闭环——回退路径属 T10 原有功能（R1 Executor 自测阶段验证过），R2 scope 明确只补 HIGH finding。

#### 状态变量/锁的异常路径（G6 mock setData 返回值未定义 / graph.render 抛错场景）

构造输入: watch([colorMode, nodesWithMastery]) 触发时，mock `setData` 是 `vi.fn()`（返回 undefined），`render` 是 `vi.fn()`（返回 undefined）

运行命令: `cd /c/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js -t "Phase 1 T10 — watch"`

实际输出:
```
 ✓ Phase 1 T10 — watch colorMode 重绘 + focus replay (F003)
   ✓ 切换 colorMode 触发 graph.setData() 重绘 ...
   ✓ focus 态下切换 colorMode：setData 之后 setElementState 被再次调用 ...
 Test Files  1 passed (1)
      Tests  41 passed (41)
```

结论: watch 内 `try { graph.setData(data); graph.render() } catch (err) { console.warn(...) }` 在 spy 返回 undefined 场景下正常走完 try 分支（不抛），F003-b 的 focus replay 断言依赖"setData 之后 setElementState 被再次调用"—— setElementState mock 亦未抛，spy calls 正常累加。生产环境真 G6 的 setData/render 返回 Promise 或 undefined 均不影响（watch 未 await）。

#### 字符串匹配/条件判断的假阴性（data-attr String(Boolean(x)) 与 undefined 混淆）

构造输入: ColorModeToggle stub 的 `data-has-student="${String(Boolean(props.hasStudent))}"`；测试读 `.attributes('data-has-student') === 'true'`

运行命令: `cd /c/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/knowledge-tree/KnowledgeTreePage.mount.test.js -t "hasStudent"`

实际输出: PASS（见 F002-b 行）

结论: `String(Boolean(undefined)) === 'false'` / `String(Boolean('s1')) === 'true'`，字符串断言避开了 truthy/falsy 歧义。反证"删 `:has-student` 绑定"后 stub 的 props.hasStudent 成 undefined，`Boolean(undefined)` → `false`，data-attr="false"——但这里测试期望"写入 s1 后是 true"，所以 fail 链路是"缺了绑定 → 永远 false → 写入响应断言 fail"，精准捕获 F001 bug。

### 语义回归自检

`semantic_risk=false`（纯前端状态合并修复 + 测试强化 + G6 mock 扩展，无 API 变更、无 schema 变更、无业务语义变更）。跳过 Fix Intent Card + Semantic Regression Gate。

### Fix Card

R2 是 R1 FAIL 的修复。按 `review-templates.md` R1→R2 修复卡：

| Finding | Category | Type | Before | After | Resolved-hypothesis | Status |
|---------|----------|------|--------|-------|---------------------|--------|
| F001 | code-bug | defect_fix | 页面本地 ref 与 composable ref 双真源；loadMastery 写 composable ref 后页面本地 ref 仍 null → mastery 永远 disabled | 页面解构 composable selectedStudentId → loadMastery 后页面立即响应，has-student=true，auto-switch 触发 | ✅ 单一真源（解构 useKnowledgeTree 导出的 selectedStudentId，删页面本地 ref） | resolved-correct |
| F002 | test-gap | defect_fix | mount.test.js stub 吞新 props；删除 `:color-mode`/`:has-student`/watch 无任何断言 fail | mount.test.js 3 个集成断言分别锁 ColorModeToggle 挂载/hasStudent 派生/auto-switch；删任一接线 → 至少 1 断言 fail（实测 3 条反证全触发 fail） | ✅ stub props 补齐 + ColorModeToggle stub + 3 个 data-attr 断言 | resolved-correct |
| F003 | test-gap | defect_fix | G6 mock 缺 setData，watch 里 setData 抛被 try/catch 吞；删 watch 整块 3 个 T10 断言全绿 | G6 mock 补 setData spy；2 个 watch 路径断言，删 watch 整块 2 fail，删 focus replay 分支仅 1 fail（精准区分） | ✅ setData spy + watch 触发断言 + focus replay 断言 | resolved-correct |

### 🔀 偏离汇总（供 reviewer 快速定位）

1. **CLAUDE.md 被 doc-sync-guard 拦截强制追加**：`KnowledgeTreePage.vue` 行追加"selectedStudentId 从 useKnowledgeTree 解构（单一真源，R2 F001 修复 state 分裂）"。变更纯追加，未改动旧描述。
2. **F002 mock 的 loadMastery 模拟真实写入**：`loadMastery: vi.fn(async (sid) => { ... mockState.selectedStudentId.value = sid })`，对齐 `useKnowledgeTree.loadMastery` 内部 `selectedStudentId.value = studentId` 语义，避免"测试用直接写 mockState.selectedStudentId" 与"handoff 描述 '调用 loadMastery' 入口"脱节；两种入口等价。
3. **F003 2 个 watch 断言**：handoff 要求 "(a) colorMode 切换触发重绘 (b) focus replay" —— 严格按 (a)/(b) 实现，未扩展到 nodesWithMastery 变化路径（共享同一 watch，覆盖 colorMode 即覆盖 watch 主干）。
4. **F003 未改 ConceptMapPanel.vue try/catch**：handoff 明确禁止。反证 F003-a 删除 watch 整块是临时操作，验证后立即恢复。

### 送审准备

1. Baseline 对齐：`npx vitest run` — **24 files / 233 tests PASS**（2026-04-14 10:04:15）
2. Staged 纯净：3 次 commit 前 `git diff --cached --name-only` 严格验证 R2 scope 文件（F001 `KnowledgeTreePage.vue + CLAUDE.md` / F002 `mount.test.js` / F003 `ConceptMapPanel.test.js`）
3. Commits: `2ab10a2` (F001) → `aab13fc` (F002) → `c5bff80` (F003)，`git log --oneline -3` 验证
4. 反证实测 5 条全部触发 fail（见反证矩阵），恢复后全绿
5. 下一步：使用 codex-review skill 进行 Batch 3.a R2 GPT 独立审查（subject_ref `commit:2ab10a2..c5bff80`）
