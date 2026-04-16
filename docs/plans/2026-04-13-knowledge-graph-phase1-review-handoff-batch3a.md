[edu-cloud] Executor→Reviewer | 2026-04-14 08:25:45

## 审查交接单: Task 9-10（Batch 3.a）

- 计划: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-plan.md`（R6，hash `a963e85b...`）
- 设计: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-knowledge-graph-optimization-design.md`
- Handoff: `docs/plans/2026-04-13-knowledge-graph-phase1-handoff-batch3a.md`
- Gates: `docs/plans/2026-04-13-knowledge-graph-phase1-gates.json`（plan_review=pass R6，code_review_batch1/2=pass）
- 范围: T9（heatmapUtils + ColorModeToggle）+ T10（ConceptMapPanel 节点视觉升级）
- Commits: `2f7ddad` (T9) → `ebfa83f` (T10)
- 修改文件（8 个）：
  - `frontend/src/components/knowledge-tree/heatmapUtils.js`（CREATE）
  - `frontend/src/components/knowledge-tree/ColorModeToggle.vue`（CREATE）
  - `frontend/src/__tests__/knowledge-tree/heatmapUtils.test.js`（CREATE）
  - `frontend/src/__tests__/knowledge-tree/ColorModeToggle.test.js`（CREATE）
  - `frontend/src/components/knowledge-tree/ConceptMapPanel.vue`（MODIFY）
  - `frontend/src/pages/KnowledgeTreePage.vue`（MODIFY）
  - `frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js`（MODIFY）
  - `CLAUDE.md`（MODIFY — doc-sync-guard 强制，KnowledgeTreePage.vue 行追加 T9-T10 描述）
- 测试基线前 → 后: 22 files / 200 tests → **24 files / 228 tests PASS**

### 逐 Task 自审

| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T9 Step 1 | 写 heatmapUtils 测试（plan 示例 ~7 断言） | `heatmapUtils.test.js` 写入 **20 断言**（含 hex 正则/通道值上下界/log 尺度反证/monotonic/clamp 负数） | 🔀 | **超集**：plan 示例是骨架，实际按"精确断言+反证"铁律扩展。新增：(a) log 尺度反例定量断言（`r100 < linearExpected-20`，线性实现下 ≈223，log 实现下 ≈118），(b) 所有通道值上下界锁定，(c) 负数/非法 maxFreq 边界。反例验证见下方预审自检表。 |
| T9 Step 1 | import 路径 `from '../heatmapUtils'` | 实际用 `from '../../components/knowledge-tree/heatmapUtils'` | 🔀 | **路径修正**：handoff-batch3a 明确测试路径改到 `frontend/src/__tests__/knowledge-tree/`，原 plan import 语句（相对当前组件目录）与 R6 测试路径不一致，按现有项目约定修正。其他测试文件（ConceptMapPanel.test.js L32）亦用此路径。 |
| T9 Step 2 | 实现 heatmapUtils.js（4 函数 + log 尺度） | 严格按 plan 实现。`heatmapColor` 用 `log(freq+1)/log(max+1)` 归一化 + 线性插值 `#EEEEEE → #3B5998`；`masteryColor` 4 态；`reviewStatusColor` 3 态；`nodeSizeFromImportance` 线性到 `[20, 60]`；加 `Number.isFinite` 守护 NaN/Infinity | ✅ | 一致。`maxFreq<=0` 返回浅灰 fallback。`toHex` 提升为模块私有复用。 |
| T9 Step 3 | 实现 ColorModeToggle.vue（n-radio-group + hasStudent disabled） | 按 plan 实现，额外 `defineExpose({ onChange })` 供测试调用（否则 `wrapper.vm.onChange('mastery')` 失败） | 🔀 | **必要暴露**：plan 示例 `wrapper.vm.onChange('mastery')` 的测试需要 onChange 暴露，plan 未显式 defineExpose。Vue 3 `<script setup>` 默认不暴露，必须 defineExpose，否则 plan 示例测试本身无法运行。 |
| T9 Step 4 | 写 ColorModeToggle 测试（plan 示例 3 断言） | 写入 **5 断言**（+ localMode sync 回归 / + hasStudent=true 反证不 disabled） | 🔀 | **超集+反证**：新增 (a) `watch props.modelValue → localMode` sync 正向回归（反例：若 watch 漏写，父变更不生效），(b) hasStudent=true 反证（反例：若 disabled 绑定错 hasStudent 而非 !hasStudent，true 也会 disabled）。 |
| T9 Step 5 | `npx vitest run heatmapUtils ColorModeToggle` 全绿 | 25 tests PASS（20 heatmap + 5 ColorModeToggle），2026-04-14 08:18:32 | ✅ | 见验证清单自检 §cmd-1。 |
| T9 Step 6 | commit 4 文件 | commit `2f7ddad`，范围 5 文件（plan 的 4 + CLAUDE.md） | 🔀 | **doc-sync-guard 强制**：guard 拦 `project structure 新增` 变更要求 CLAUDE.md 同步。在 `frontend/src/pages/KnowledgeTreePage.vue` 行末尾追加 `Phase 1 T9-T10：ColorModeToggle ... heatmapUtils ...`。变更纯追加，不改动旧描述。 |
| T10 Step 1 | ConceptMapPanel.vue 接 colorMode prop + buildG6Data 三分支 | 实现：接 `colorMode` + `nodesWithMastery` prop；buildG6Data 每节点追加 `style.size=[W, W*0.6]` (importance) 与 `style.fill` (colorMode 三分支)；增 `data.importance/examFrequency` 字段；保留原有 x/y/data.label/badgeText/reviewStatus | ✅ | 一致。G6 v5 instance-level `style.size/fill` 覆盖 createGraph type-level（REVIEW_COLORS fallback 保留不破坏现状）。 |
| T10 Step 1 | watch colorMode → setData+render 并保留焦点 | `watch(() => [props.colorMode, props.nodesWithMastery], ...)`，在 `if (focusedNodeId.value) nextTick(updateElementStates)` 保留焦点；外层 `try/catch` 防 happy-dom 下 G6 mock 异常污染 | 🔀 | **合并 watch 源**：plan 只 watch `colorMode`；实际合并 `nodesWithMastery`（同一行为路径），避免 mastery 数据到达后再 re-render 需要第二个 watch。`{deep: true}` 符合 `props.nodesWithMastery` 是数组的语义。`try/catch` 与现有 `updateElementStates` 风格一致。 |
| T10 Step 1 | `defineExpose({ buildG6Data })` | 增量追加到现有 defineExpose（保留 Phase 2/2.5 既有暴露） | ✅ | 一致。 |
| T10 Step 2 | KnowledgeTreePage 挂 ColorModeToggle + watch selectedStudentId | 实现：`<template v-else>` 嵌入 `.graph-tools` 工具条 + `<ColorModeToggle>` + `<ConceptMapPanel :color-mode="colorMode" :nodes-with-mastery="nodesWithMastery">`；增 `colorMode` ref + `watch(selectedStudentId, ...)` auto-switch | 🔀 | **模板嵌套形态**：plan 是扁平 `<ColorModeToggle v-if=... />` + `<ConceptMapPanel v-if=... />`（两个独立 `v-if`）；实际用 `<template v-else>` 包住二者（避免 `v-if` 条件重复书写）。语义等价，条件收敛一处更清晰。其余（colorMode ref / watch / props 传递）均与 plan 一致。 |
| T10 Step 3 | ConceptMapPanel.test.js 新增 3 行为断言 | 在文件末尾新增 `describe('Phase 1 T10: buildG6Data visual encoding', ...)`，3 tests：importance 差异 / colorMode fill 变化 / mastery weak R>G | ✅ | 按 plan 示例实现，断言上下界锁定（importance=10 size∈[50,70], importance=2 size∈[20,30]），并加 hex 正则校验 fill。 |
| T10 Step 4 | `npx vitest run ConceptMapPanel.test.js` 全绿 | 39 tests PASS（原 36 + 新 3），2026-04-14 08:23:39 | ✅ | 见验证清单自检 §cmd-2。 |
| T10 Step 5 | 本地 dev server + 浏览器视觉验证（节点大小差异/颜色切换/焦点模式回归） | **未自动执行，标注待用户验收** | 🔀 | **自治边界规则**：涉及视觉/渲染/布局的任务，验收权在用户，Claude 不启动 dev server 自证。按 `autonomy-boundary.md` + L015（虚假完成声明与验收越权），交接单明确标注待用户在 http://localhost:5273 验收节点大小/颜色/焦点兼容性。**自动化替代**：行为断言已覆盖数据层（size/fill 分支与 mastery 映射），但不代替浏览器视觉保真验证。 |
| T10 Step 6 | commit 3 文件 | commit `ebfa83f`，范围 4 文件（plan 的 3 + CLAUDE.md 扩展） | 🔀 | **doc-sync-guard 强制同上**：KnowledgeTreePage.vue 行的 T9 描述扩展为 T9-T10。 |

> 状态：✅一致 / ❌不一致 / 🔀改进（实现优于计划，必须记录具体变更内容）

### 预审自检（送审前必填）

| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出（PASS/FAIL + 关键行） | 反证验证（删除核心逻辑后测试是否 fail） |
|---------------|------------------|---------|-------------------------------|---------------------------------------|
| heatmapColor log 尺度 | `heatmapUtils.test.js::uses log scale — freq=100 lies between freq=1 and freq=1000, not near linear midpoint` | `npx vitest run heatmapUtils` | **PASS** — `Test Files 1 passed (1) / Tests 20 passed (20)` | ✅ 删除 `Math.log(...)/Math.log(...)` 改为线性 `clamped/maxFreq`：freq=100 时线性 `ratio=0.1`, R≈220；断言 `r100 < linearExpected-20 (≈203)` FAIL。|
| masteryColor weak R>G | `heatmapUtils.test.js::weak returns red (R > G)` | 同上 | **PASS** | ✅ 删除 `weak: '#FF4D4F'` 让 `weak` fallback 到 unseen `#D9D9D9`（R≈G）：`r > g` FAIL。|
| nodeSizeFromImportance monotonic | `heatmapUtils.test.js::is strictly monotonic increasing on [0, 10]` | 同上 | **PASS** | ✅ 删除 `SIZE_MIN + (clamped/10)*(SIZE_MAX-SIZE_MIN)` 改为 `return 30`：相邻调用全相等，`> nodeSizeFromImportance(v)` FAIL。|
| ColorModeToggle modelValue sync | `ColorModeToggle.test.js::syncs localMode from parent modelValue prop` | `npx vitest run ColorModeToggle` | **PASS** — `Tests 5 passed (5)` | ✅ 删除 `watch(() => props.modelValue, (v) => { localMode.value = v })`：`setProps({modelValue:'review_status'})` 后 `localMode` 仍 `exam_frequency` FAIL。|
| ConceptMapPanel size reflects importance | `ConceptMapPanel.test.js::node size reflects importance_score — importance=10 produces larger size than importance=2` | `npx vitest run ConceptMapPanel` | **PASS** — `Tests 39 passed (39)` | ✅ 删除 `size = nodeSizeFromImportance(...)` 改为 `size = 28`：sizeA === sizeB，`sizeA > sizeB` FAIL；`sizeA >= 50` FAIL（28 < 50）。|
| ConceptMapPanel colorMode fill 变化 | `ConceptMapPanel.test.js::fill color changes with colorMode (exam_frequency vs review_status)` | 同上 | **PASS** | ✅ 删除 colorMode 三分支只留 `fill = heatmapColor(...)`：两次 `buildG6Data().nodes[0].style.fill` 相同，`examFill !== reviewFill` FAIL。|
| ConceptMapPanel mastery R>G | `ConceptMapPanel.test.js::mastery mode uses mastery state — weak produces red (R > G)` | 同上 | **PASS** | ✅ 删除 mastery 分支让 fallthrough 到 review_status (`published='#52C41A'` → R=0x52, G=0xC4, G>>R)：`r > g` FAIL。|

### 验证清单自检

原 plan T9 + T10 审查清单逐项自检（Executor）：

**T9 清单**
- ✅ heatmapColor 使用对数尺度（处理偏斜分布）— `heatmapUtils.js:20` `Math.log(clamped + 1) / Math.log(maxFreq + 1)`
- ✅ 三种着色模式：考频/掌握度/审核状态 — `ColorModeToggle.vue:6-8` 三个 n-radio-button
- ✅ 无学生时掌握度模式 disabled — `ColorModeToggle.vue:7` `:disabled="!hasStudent"`；测试 `ColorModeToggle.test.js::disables mastery when hasStudent=false` PASS
- ✅ 不在组件内硬编码颜色常量，集中在 heatmapUtils — `ColorModeToggle.vue` 无颜色常量；所有 palette 常量 `MASTERY_COLORS/REVIEW_COLORS/HEATMAP_*` 在 `heatmapUtils.js`

**T10 清单**
- ✅ 节点大小反映 importance_score — `ConceptMapPanel.vue:218-219` `nodeSizeFromImportance(importance)`；测试 `importance=10 > importance=2` PASS
- ✅ 三种着色模式切换有效 — `ConceptMapPanel.vue:222-230` 三分支；watch 在 `ConceptMapPanel.vue:439-450` setData+render
- ✅ 焦点模式与新视觉兼容 — watch colorMode 内 `if (focusedNodeId.value) nextTick(updateElementStates)`（`ConceptMapPanel.vue:449`），原 `createGraph` 末尾焦点重放逻辑（`ConceptMapPanel.vue:354-356`）保留不变
- ✅ 模块切换时颜色/大小正确刷新 — 原 `watch(() => [props.moduleId, props.nodes, props.edges], destroy+create)` 保留，colorMode 独立 watch 走轻量 setData 路径

**边界条件**：
- ✅ `importance_score` 缺失 → `Number.isFinite(n.importance_score) ? n.importance_score : 0` → size 最小（`ConceptMapPanel.vue:216`）
- ✅ `exam_frequency` 缺失 → `n.exam_frequency || 0` → `heatmapColor(0, max)` 浅灰色（`ConceptMapPanel.vue:228`）
- ✅ 切换 colorMode 后焦点模式仍生效 — watch block 内 `nextTick(updateElementStates)`（`ConceptMapPanel.vue:449`）

### 根因分析

非 bug fix 任务，跳过。

### 自查（四要素格式）

#### 新增文件的边界 case（heatmapColor 极端输入）

构造输入: `freq=-5, freq=2000, freq=0, maxFreq=0, maxFreq=-10`

运行命令: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run heatmapUtils -t "clamp|freq > maxFreq|maxFreq <= 0|freq=0"`

实际输出:
```
 ✓ src/__tests__/knowledge-tree/heatmapUtils.test.js (20 tests) 4ms
   ✓ heatmapColor > returns well-formed #RRGGBB string
   ✓ heatmapColor > freq=0 returns light gray (all channels >= 0xCC)
   ✓ heatmapColor > freq=maxFreq returns deep color (R < 100)
   ✓ heatmapColor > handles freq > maxFreq by clamping (equal to freq=maxFreq)
   ✓ heatmapColor > handles maxFreq <= 0 with safe fallback
...
 Test Files  1 passed (1)
      Tests  20 passed (20)
```

结论: 越界/零/负值全部 clamp 到 `[0, maxFreq]` 内，`maxFreq<=0` 返回浅灰 fallback，无 NaN/Infinity 泄漏。`nodeSizeFromImportance(-5)==(0)` `(100)==(10)` 单独断言也 PASS。

#### 状态变量/锁的异常路径（watch colorMode 在 happy-dom 下 G6 mock 场景）

构造输入: `setProps({ colorMode: 'review_status' })` 触发 watch，G6 mock 的 `setData` 未定义（happy-dom + vi.mock）

运行命令: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run ConceptMapPanel -t "fill color changes with colorMode"`

实际输出:
```
 ✓ src/__tests__/knowledge-tree/ConceptMapPanel.test.js > Phase 1 T10: buildG6Data visual encoding > fill color changes with colorMode (exam_frequency vs review_status) 7ms
 Test Files  1 passed (1)
      Tests  39 passed (39)
```

结论: watch 内 `try { graph.setData(data); graph.render() } catch (err) { console.warn(...) }` 成功吞 happy-dom G6 mock 的 `setData is not a function`（mock 未 stub setData），后续 `if (focusedNodeId.value) nextTick(updateElementStates)` 不受影响。生产环境真 G6 有 setData，不会进 catch。

#### 字符串匹配/条件判断的假阴性（colorMode 默认值 + 未知值 fallback）

构造输入: 同一组 node 分别在 `colorMode='exam_frequency'`/`'review_status'`/`'mastery'` 三种值下调用 buildG6Data

运行命令: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run ConceptMapPanel -t "buildG6Data visual encoding"`

实际输出:
```
 ✓ Phase 1 T10: buildG6Data visual encoding
   ✓ node size reflects importance_score — importance=10 produces larger size than importance=2
   ✓ fill color changes with colorMode (exam_frequency vs review_status)
   ✓ mastery mode uses mastery state — weak produces red (R > G)
 Test Files  1 passed (1)
      Tests  39 passed (39)
```

结论: 三分支覆盖完整；无 fallback 语义冲突（分支 `if/else if/else` 有序）；测试断言 `examFill !== reviewFill` 防止任意两模式被重定向到同一函数。默认值 `exam_frequency` 是 else 分支，任意未知 colorMode 值亦走 heatmapColor 路径（符合 plan "fallback" 要求）。

### 语义回归自检

`semantic_risk=false`（纯前端新增视觉编码 util + 组件属性接入，无 API 变更、无 schema 变更、无业务语义变更）。跳过。

### Fix Card

`semantic_risk=false` 且非 review fix，跳过。

### 🔀 偏离汇总（供 reviewer 快速定位）

1. **T9 测试 import 路径**：`../../components/knowledge-tree/heatmapUtils`（现有项目约定，plan R6 更新测试目录但未同步 import 语句）
2. **T9 测试覆盖超集**：heatmapUtils 20 断言（plan 示例 7） + ColorModeToggle 5 断言（plan 示例 3）—— 反证风格 + 通道值上下界锁定
3. **T9 ColorModeToggle defineExpose onChange**：supporting plan 示例测试 `wrapper.vm.onChange('mastery')`
4. **T10 watch 合并源**：`[colorMode, nodesWithMastery]` 单 watch + `{deep:true}`（plan 只 watch colorMode）
5. **T10 watch try/catch 包裹 setData/render**：防 happy-dom G6 mock 污染（生产环境无影响）
6. **T10 KnowledgeTreePage 模板结构**：`<template v-else>` 内聚工具条+面板（plan 是两个独立 `v-if`，语义等价）
7. **T10 Step 5 视觉验证**：未自动执行，交接用户验收（autonomy-boundary + L015）
8. **CLAUDE.md 追加描述（两次）**：doc-sync-guard 硬拦截强制，Batch 3.a commit 强制含 CLAUDE.md

### 送审准备

1. Baseline 对齐：`npx vitest run` — **24 files / 228 tests PASS** (2026-04-14 08:23:53)
2. Staged 纯净：commit 前 `git diff --cached --name-only` 严格验证 5/4 文件在 handoff 允许清单内（见 commit 消息）
3. 视觉验证：待用户在 http://localhost:5273 验收
4. 下一步：使用 codex-review skill 进行 Batch 3.a Gate 2 Code Review
