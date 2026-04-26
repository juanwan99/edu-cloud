[edu-cloud] GPT Reviewer | 2026-04-14 10:23:55

<!-- anchor: finding-classification -->
## 审查报告: Batch 3.a Round 2（F001 + F002 + F003 修复）

- 结论: **PASS**
- Reviewer: GPT Codex (gpt-5.4)
- Subject: commits `2ab10a2..c5bff80`（R2 修复：F001 KnowledgeTreePage.vue + F002 mount.test.js + F003 ConceptMapPanel.test.js；含 CLAUDE.md 被 doc-sync-guard 强制同步）
- Raw output: `docs/plans/.codex-code-review-batch3a-r2-raw.log`（SHA256 `188103a159567f9ab1a8b691821e8c31af2d28d2b806ad1580487f9908fdeb6a`）
- Range diff hash: `4a2d5182e89ed2f28cf31850d9dfd39e137af7eb4d714c1621860d960db75d8b`
- 交接单: `docs/plans/2026-04-13-knowledge-graph-phase1-review-handoff-batch3a-r2.md`
- R1 FAIL 报告: `docs/plans/2026-04-13-knowledge-graph-phase1-review-report-batch3a.md`
- R2 Handoff directive: `docs/plans/2026-04-13-knowledge-graph-phase1-handoff-batch3a-r2.md`

## 变更理解

R2 修复 R1 的 3 个 HIGH finding：

- **F001 (code-bug, defect_fix)**：KnowledgeTreePage 从 `useKnowledgeTree` 解构 `selectedStudentId`（composable 已导出），删除页面本地 `const selectedStudentId = ref(null)`，消除双真源 state 分裂。`useKnowledgeTree.js` 未动（handoff 铁律）。

- **F002 (test-gap, defect_fix)**：`KnowledgeTreePage.mount.test.js` stub 升级——mockState 追加 `selectedStudentId` ref + `loadMastery` mock 真实写入；ConceptMapPanel stub props 补 `colorMode/nodesWithMastery` + data-attr；新增 ColorModeToggle stub；新增 3 个真实挂载集成断言（scope R2 扩容 1 文件，Planner 批准）。

- **F003 (test-gap, defect_fix)**：`ConceptMapPanel.test.js` G6 mock 补 `setData` spy；新增 2 个 watch 路径断言（入口是 `wrapper.setProps({colorMode})` 真触发 watch，非纯函数 `buildG6Data()`）。`ConceptMapPanel.vue` 的 try/catch 严格未动（handoff 禁止）。

## 对抗性审查

GPT 以独立审查者身份执行 5 次 mutant 验证（删除生产代码后观察测试红色度）：

1. 删 `KnowledgeTreePage.vue:50 :has-student` → "composable selectedStudentId 写入后 hasStudent=true" 1/1 fail（`expected 'false' to be 'true'`）
2. 删 `KnowledgeTreePage.vue:61 :color-mode` → "进入 Mx 模块" + "auto-switch" 2/2 fail（`data-color-mode` 变 `undefined`）
3. 删 `KnowledgeTreePage.vue:121 watch(selectedStudentId)` auto-switch → "auto-switch" 1/1 fail（`exam_frequency` 未切 `mastery`）
4. 删 `ConceptMapPanel.vue:449` watch 整块 → 2 新断言全 fail（`graph.setData.mock.calls.length` 未增长）
5. 仅删 watch 内 `focusedNodeId` replay 分支 → 仅 "focus replay" 1/2 fail，重绘用例仍绿（区分度成立）

`git diff --name-only 2ab10a2~1..c5bff80 -- frontend/src/components/knowledge-tree/useKnowledgeTree.js frontend/src/components/knowledge-tree/ConceptMapPanel.vue` 返回为空 —— 生产代码铁律遵守。

## Phase 0 — Contract Pack 验证

R2 没有偏离 R6 Plan Contract Pack。变更面仍是 3 个修复点，对外行为没有新增 public API；`CLAUDE.md` 变更只是 doc-sync-guard 强制同步（KnowledgeTreePage 行追加"selectedStudentId 单一真源"描述）。`git diff --stat 2ab10a2~1..c5bff80` 仅 4 文件，真正代码面 1 页面 + 2 测试文件。

## Phase 1 — 测试充分性

三个 finding 的修复均通过 mutant 测试验证 —— R2 新增 5 个断言在删除对应生产代码后都能红色触发，非逻辑镜像：
- F002 断言入口走真实 `mount(KnowledgeTreePage)` + stub data-attr 读回，非 `wrapper.vm.<exposed>` 纯函数
- F003 断言入口走 `wrapper.setProps({colorMode})` 真触发 watch，非直接调 `wrapper.vm.buildG6Data()`

反证精准区分：删 watch 整块 → 2 fail；只删 focus replay 分支 → 仅 1 fail，区分度成立。

## Phase 2 — 行为正确性与回归

- F001 未引入新 ref 身份或时序回归。`watch(selectedStudentId)`、`:has-student`、`studentId` computed 均绑定 composable 导出的同一 ref；`useKnowledgeTree.js` 未动，行为边界无扩张
- F002 的新 mock `loadMastery` 写入 `selectedStudentId` 的语义与真实 `useKnowledgeTree.loadMastery:37` 一致，不制造假阳性
- F003 `graph.setData = vi.fn()` 返回 `undefined`，组件 watch 顺序调 `setData(); render()` 不依赖返回值，`try` 分支可完整走完；`ConceptMapPanel.vue` 的 try/catch 完整保留

## Phase 3 — 未测试风险

`rg "selectedStudentId\s*=\s*ref\(" frontend/src` 仅命中 `useKnowledgeTree.js:13`（composable 内部） 和无关的 `AnalyticsTrendPage.vue:62`。knowledge-tree 代码内 R1 同名双真源模式未再出现。

存在一个小边界未显式覆盖：R2 未新增"学生清空后从 `mastery` 回退到 `exam_frequency`"的断言（逆向 auto-switch 路径）。不影响 F001/F002/F003 修复闭环，也不构成新 HIGH/MED finding。

---

<!-- anchor: finding-type -->

## 发现清单

### F001 — KnowledgeTreePage selectedStudentId 单一真源

- ID: F001
- Severity: HIGH
- Category: code-bug
- Type: defect_fix
- Status: **resolved-correct**
- Inv-conflict: none
- Before-behavior: 页面本地 `selectedStudentId` 与 composable 内部 ref 双真源；`loadMastery()` 写 composable ref 后，页面 `:has-student` / auto-switch 仍读本地 ref，掌握度模式不可用
- After-behavior: 页面直接解构 composable 的 `selectedStudentId`；`watch(selectedStudentId)` / `:has-student` / `studentId` computed / `loadMastery` 调用链路全部指向同一 ref
- R1 Evidence: R1 报告指出页面解构遗漏 + 本地 ref 自建
- R2 Evidence: `frontend/src/pages/KnowledgeTreePage.vue:108` 解构包含 `selectedStudentId`；`KnowledgeTreePage.vue:121` `watch(selectedStudentId)` 直接监听该 ref；`KnowledgeTreePage.vue:50` `:has-student` 与 `KnowledgeTreePage.vue:140` `studentId` computed 消费同一源；`useKnowledgeTree.js:13/:37/:81` 保持原样（composable 本已导出并写入该 ref）
- Impact: R1 的 state split 已闭合，掌握度可用性恢复
- 独立 mutant 验证: 删 `:has-student` 后 `mount.test.js::composable selectedStudentId 写入后 hasStudent=true` 1/1 fail（`expected 'false' to be 'true'`）
- 半修捕获能力: "只加解构不删本地 ref" → 同作用域重复声明，编译失败；"只删本地 ref 不加解构" → 引用未定义，编译失败 —— 两种半修都不会静默漏过

### F002 — KnowledgeTreePage.mount.test.js 集成层接线断言

- ID: F002
- Severity: HIGH
- Category: test-gap
- Type: defect_fix
- Status: **resolved-correct**
- Inv-conflict: none
- Before-behavior: stub 吞 T10 新 props；未 import/register ColorModeToggle；整文件无 `selectedStudentId/hasStudent/colorMode` 断言；删接线仍全绿
- After-behavior: 真实 `mount(KnowledgeTreePage)` + stub data-attr 观察页面接线；删任一核心接线都会红
- R1 Evidence: 页面级 stub 缺 `colorMode/nodesWithMastery`；无 ColorModeToggle 入口
- R2 Evidence: `mount.test.js:51` mock composable 返回 `selectedStudentId`；`mount.test.js:66` `loadMastery` mock 写入该 ref；`mount.test.js:172` ConceptMapPanel stub props 补齐 `colorMode/nodesWithMastery` + `data-color-mode`；`mount.test.js:195` ColorModeToggle stub 注册 + `.color-mode-toggle-stub`；`mount.test.js:463` 起 3 新真实挂载断言
- Impact: 页面接线有效回归保护
- 独立 mutant 验证（3 条）：
  - 删 `:has-student` → "composable selectedStudentId 写入" 1/1 fail
  - 删 `:color-mode` → "进入 Mx 模块" + "auto-switch" 2/2 fail
  - 删 auto-switch watch → "auto-switch" 1/1 fail
- Mock 语义对齐: `loadMastery` mock 的"写 selectedStudentId"与真实 `useKnowledgeTree.loadMastery:37` 一致，不制造假阳性

### F003 — ConceptMapPanel.test.js G6 mock setData + watch 路径断言

- ID: F003
- Severity: HIGH
- Category: test-gap
- Type: defect_fix
- Status: **resolved-correct**
- Inv-conflict: none
- Before-behavior: G6 mock 缺 `setData`，watch 路径被 try/catch 吞；T10 断言只走 `buildG6Data()` 纯函数，删 watch 整块仍全绿
- After-behavior: G6 mock 具备 `setData` spy；测试通过 `setProps` 真实触发 watch，分别锁"重绘"和"focus replay"
- R1 Evidence: watch 路径未触发，setData 未 mock
- R2 Evidence: `ConceptMapPanel.test.js:9` G6 mock 补 `setData = vi.fn()`；`ConceptMapPanel.test.js:897` 起 2 新 watch 路径用例，入口是 `wrapper.setProps({ colorMode })`；`ConceptMapPanel.vue:449` watch 代码与 `ConceptMapPanel.vue:452` try/catch 保持未改
- Impact: setData/render + focus replay 有了真入口回归保护
- 独立 mutant 验证（2 条）：
  - 删整块 watch → 2/2 fail（两条都因 `graph.setData.mock.calls.length` 未增长而红）
  - 仅删 focus replay 分支 → 1/2 fail（只 focus replay 用例红，重绘用例仍绿，区分度成立）
- 行为保留: try/catch 内 `setData(); render()` 不依赖返回值，`vi.fn()` 返回 undefined 不抛；真 G6 亦返回 undefined/Promise，watch 语义一致

---

<!-- anchor: pass-fail -->
## PASS/FAIL 判定

- F001 (HIGH code-bug) **resolved-correct** ✓
- F002 (HIGH test-gap) **resolved-correct** ✓
- F003 (HIGH test-gap) **resolved-correct** ✓
- 新增 HIGH/MED finding: 无
- 新增 LOW finding: 无（Phase 3 提到的"学生清空逆向 auto-switch"未构成 finding）

综合：**Round 2 PASS**

## 行为变更审批记录

本轮**无 behavior_change finding**（3 个全部为 defect_fix；R2 修复严格在 R1 defect_fix 范围内）。无需用户按 intent-guard 分组批准。

## 下一步

1. ✅ gates.json `code_review_batch3a` 回执：R1 FAIL → R2 PASS
2. ✅ Batch 3.a Gate 2 闭环，可推进到 Batch 3.b（按 plan R6 后续 Task）
3. 长期 deferred（本轮无阻塞）：
   - 学生清空后从 `mastery` 回退到 `exam_frequency` 的断言——若后续涉及回退行为变更可补；本批次不必须
