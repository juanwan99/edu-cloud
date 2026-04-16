---
type: handoff
round: R2 (Gate 2 Code Review 第二轮)
created: 2026-04-14 08:45:00
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-knowledge-graph-optimization-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-plan.md
prev_handoff: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-handoff-batch3a.md
r1_review: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-review-report-batch3a.md
r1_handoff: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-review-handoff-batch3a.md
batch: 3.a (R2)
---

# R1 FAIL 3 HIGH finding 处置方案（Planner 决策）

## 结论：R2 修复全部 3 finding（F001 + F002 + F003）

Planner 对每个 finding 独立核查代码状态，修订了 Executor 对 scope 的判断。

## F001 HIGH code-bug — **Planner 纠正 Executor 误判**

### Executor R1 分析的错误

Executor 在 review-report R2 处置建议中写："F001 修复要触 `useKnowledgeTree.js`（handoff 严禁修改）"。

### 真实情况（Planner 核查）

**`useKnowledgeTree.js` 已经导出 `selectedStudentId`**：
```javascript
// useKnowledgeTree.js:13
const selectedStudentId = ref(null)
// ...
// useKnowledgeTree.js:37-38
async function loadMastery(studentId, module = 'all') {
  selectedStudentId.value = studentId  // composable 内部写入
  // ...
}
// useKnowledgeTree.js:81
return {
  navigationData, graphData, masteryData, qualityIssues, qualitySummary,
  modulesQuality,
  loading, selectedModule, selectedStudentId, moduleMastery, nodesWithMastery,
  //                      ^^^^^^^^^^^^^^^^^^ 已导出
  loadGraph, loadMastery, loadQuality, loadAllModulesQuality, applyEdit,
}
```

**`KnowledgeTreePage.vue:108-112` 的解构遗漏了它**：
```javascript
const {
  navigationData, graphData, loading, selectedModule, moduleMastery,
  nodesWithMastery, qualityIssues, modulesQuality,
  // ^^^ 缺 selectedStudentId
  loadGraph, loadMastery, loadQuality, loadAllModulesQuality, applyEdit,
} = useKnowledgeTree()
```

然后 line 119 自建本地 ref：`const selectedStudentId = ref(null)`。

### F001 修复指引（scope 内，仅动 1 文件）

**文件**：`frontend/src/pages/KnowledgeTreePage.vue`（已在 handoff 7 文件清单）

**改动**：
1. Line 108-112 解构列表里加入 `selectedStudentId`
2. 删除 Line 119 `const selectedStudentId = ref(null)`
3. Line 123-129 `watch(selectedStudentId, ...)` 保留（引用的是同名 ref，自动切换到 composable 导出的那个）
4. Line 50 `:has-student="!!selectedStudentId"` 保留（同名引用）
5. Line 142-145 `studentId computed` 保留（同名引用）

**禁止修改 `useKnowledgeTree.js`**。

### F001 测试补强

新增 1 个页面级集成测试（合并进 F002 修复）：
- 调用 `loadMastery('student_id')` 后，`selectedStudentId` 值变化
- `hasStudent=true`，ColorModeToggle 的 mastery 模式 `disabled=false`
- `watch selectedStudentId` 触发，colorMode 自动切换到 `mastery`

测试文件：`frontend/src/__tests__/knowledge-tree/KnowledgeTreePage.mount.test.js`（见 F002）

## F002 HIGH test-gap — **Scope 扩容 1 文件**

### 扩容后 scope 白名单（8 文件）

原 handoff-batch3a 7 文件 + **`frontend/src/__tests__/knowledge-tree/KnowledgeTreePage.mount.test.js`**（新增 MODIFY）

### F002 修复指引

**文件**：`frontend/src/__tests__/knowledge-tree/KnowledgeTreePage.mount.test.js`

**改动**：
1. Line 167-168 ConceptMapPanel stub 的 props 列表追加 `colorMode`、`nodesWithMastery`（当前缺失导致 stub 静默吞掉新 prop）
2. import `ColorModeToggle` 并在 stub 注册表里添加
3. 新增 3 个页面级集成断言：
   - **a) 删除接线必须红**：mount 后断言 `wrapper.findComponent(ColorModeToggle).exists() === true`，再断言 `wrapper.findComponent(ConceptMapPanel).props('colorMode')` 值正确
   - **b) hasStudent 派生正确**：初始状态 `ColorModeToggle` 的 `hasStudent=false`；调用 `useKnowledgeTree` 暴露的 `loadMastery('student_id')` 后 `hasStudent=true`
   - **c) auto-switch 到 mastery**：`selectedStudentId` 写入后（通过 `loadMastery`），watch 触发，ConceptMapPanel 收到的 `colorMode` 从 `exam_frequency` 变为 `mastery`

### F002 反证要求

Executor 必须在交接单「反证验证」列记录：
- 临时删除 `KnowledgeTreePage.vue:50` 的 `:has-student="!!selectedStudentId"` 绑定 → 测试必须 fail（哪个断言）
- 临时删除 `:color-mode="colorMode"` 绑定 → 测试必须 fail
- 临时删除 `watch(selectedStudentId, ...)` → auto-switch 断言必须 fail
改完验证后**必须改回**。

## F003 HIGH test-gap — **scope 内**

### F003 修复指引

**文件**：`frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js`（已在 handoff 7 文件清单，MODIFY）

**改动**：
1. Line 8-26 G6 mock 扩展：追加 `setData` spy（`vi.fn()`）
2. 新增 2 个 watch 路径测试：
   - **a) colorMode 切换触发重绘**：mount 后 `setProps({colorMode: 'review_status'})` → `await flushPromises()` → 断言 `mockGraph.setData` 被调用 ≥1 次，且入参是 `buildG6Data()` 新返回值
   - **b) focus replay**：mount 后模拟 click 节点（设置 `wrapper.vm.focusedNodeId = 'A'`）→ `setProps({colorMode: 'mastery'})` → 断言 `mockGraph.setElementState` 在 setData 之后被再次调用（重放焦点态）
3. 移除组件里 `watch` 中的 `try/catch` 静默吞异常（评审：`ConceptMapPanel.vue:444-446` 的 try/catch 应仅处理合理失败路径，不应吞掉 `setData is not a function` 这类 mock 缺失错误）
   - **等等**：修改 `ConceptMapPanel.vue` 的 try/catch 是行为改变，可能影响生产路径。**Executor 不要改 vue 文件的 try/catch**，只需让 mock 暴露 setData 使测试能观察调用即可

### F003 反证要求

交接单「反证验证」列记录：
- 临时删除 `ConceptMapPanel.vue:439-454` 整个 `watch([colorMode, nodesWithMastery], ...)` → 新 2 个测试必须全 fail
- 临时删除 watch 内部的 `updateElementStates(focusedNodeId.value)` → focus replay 测试必须 fail

## R2 扩容后 scope 白名单（8 文件）

| 文件 | 操作 | 对应 Finding |
|------|------|------------|
| `frontend/src/components/knowledge-tree/heatmapUtils.js` | 不变（T9 已 commit） | - |
| `frontend/src/components/knowledge-tree/ColorModeToggle.vue` | 不变（T9 已 commit） | - |
| `frontend/src/__tests__/knowledge-tree/heatmapUtils.test.js` | 不变 | - |
| `frontend/src/__tests__/knowledge-tree/ColorModeToggle.test.js` | 不变 | - |
| `frontend/src/components/knowledge-tree/ConceptMapPanel.vue` | **禁止修改**（T10 已 commit，F003 只改测试） | - |
| `frontend/src/pages/KnowledgeTreePage.vue` | MODIFY | F001 |
| `frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js` | MODIFY | F003 |
| **`frontend/src/__tests__/knowledge-tree/KnowledgeTreePage.mount.test.js`** | **MODIFY (R2 扩容)** | F002 |

**严禁修改**：
- `useKnowledgeTree.js`（F001 不需要动它）
- `ConceptMapPanel.vue` 的 watch try/catch（行为变更风险）
- 其他任何非上述 8 文件

Commit 前必跑 `git diff --cached --name-only` 确认只含 3 个 MODIFY 文件（其他 5 个已在 T9/T10 commit 里）。

## R2 commit 策略

建议 3 个独立 commit（或合并为 1 个），便于审查：

1. `fix(frontend): F001 KnowledgeTreePage selectedStudentId 单一真源 (kg-phase1 batch 3.a R2)`
2. `test(frontend): F002 mount.test.js 集成层接线断言 + stub props 补齐 (kg-phase1 batch 3.a R2)`
3. `test(frontend): F003 ConceptMapPanel.test.js watch colorMode 重绘 + focus replay (kg-phase1 batch 3.a R2)`

## R2 审查约束

- **Gate 2 总轮次上限 3**，R1 已用（FAIL），**R2 和 R3 还可用**
- 若 R2 PASS 直接推 Batch 3.b
- 若 R2 FAIL：按 plan review-templates.md「FAIL 升级」— 2 轮后 Planner 分类处置（code-bug 必修 R3 / design-concern 入 design.md §待处置）

## R2 审查交接单

- **文件**：`docs/plans/2026-04-13-knowledge-graph-phase1-review-handoff-batch3a-r2.md`
- **commit**：`review: kg-phase1 batch 3.a R2 审查交接单`
- **逐 Task 自审表**：按 F001/F002/F003 分段，每段列 before/after/反证实测输出
- **预审自检表**：每个新测试 slice 记录入口 + 反证验证输出（删除行为后测试 fail 的实际输出）

---

# 启动 Prompt（Executor R2）

```
[edu-cloud] Executor R2 | 2026-04-14 08:45:00
项目目录: C:\Users\Administrator\edu-cloud
Tier: T3 / Batch 3.a Round 2

读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-handoff-batch3a-r2.md（R2 指令，覆盖 R1 handoff 的 scope 约束）
参考 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-review-report-batch3a.md（R1 FAIL 报告）

R2 范围：修 F001 + F002 + F003 三个 HIGH finding。Planner 已纠正 Executor R1 对 F001 的 scope 误判——F001 完全在 scope 内（只动 KnowledgeTreePage.vue，useKnowledgeTree.js 已导出 selectedStudentId）。Scope 扩容 1 文件（KnowledgeTreePage.mount.test.js 用于 F002）。

修复指引按 handoff-batch3a-r2：
- F001: KnowledgeTreePage.vue:108 解构 selectedStudentId + 删 line 119 本地 ref，不改 useKnowledgeTree.js
- F002: mount.test.js stub 升级 (colorMode/nodesWithMastery props) + 3 个集成断言 + 3 类反证验证
- F003: ConceptMapPanel.test.js G6 mock 补 setData spy + 2 个 watch 路径断言 + 2 类反证验证；不改 ConceptMapPanel.vue 的 try/catch

scope_guard: commit 前 git diff --cached --name-only 确认 3 个 MODIFY 文件（KnowledgeTreePage.vue + ConceptMapPanel.test.js + KnowledgeTreePage.mount.test.js）

完成后输出审查交接单到 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-review-handoff-batch3a-r2.md 并 commit。使用 codex-review skill 进行 GPT 代码审查（R2 模式）。
```
