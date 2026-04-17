[edu-cloud] Executor→Reviewer | 2026-04-17 22:35:00

## R1 审查交接单: Batch 3.b（T11 NodeDetailDrawer + T12 TreeNavPanel）

### 元信息

- 计划: `docs/plans/2026-04-13-knowledge-graph-phase1-plan.md`（R6 PASS，subject_hash `a963e85b`）
- 设计: `docs/plans/2026-04-12-knowledge-graph-optimization-design.md`
- 前序 handoff（任务详情源）: `docs/plans/2026-04-13-knowledge-graph-phase1-handoff-batch3b.md`
- 并行执行卡（硬约束）: `docs/plans/2026-04-17-w2-kg-batch3b-exec-handoff.md`
- Gates: `docs/plans/2026-04-13-knowledge-graph-phase1-gates.json`（plan_review=pass R6 / batch1=pass / batch2=pass / batch3a=pass R2 / **batch3b=R1 待审**）
- R1 范围: T11 (NodeDetailDrawer + ExamItemsTab + StudyUnitTab + api 扩展) + T12 (TreeNavPanel 双模式 + buildChapterTree)
- R1 Commits:
  - `f2e9ba9` T11 code（6 files, +255）
  - `191a169` T11 CLAUDE.md 补 commit（1 file, +1/-1, L015 平账）
  - `5607a9a` T12 code + CLAUDE.md（4 files, +223/-6）
- Worktree: `/home/ops/projects/edu-cloud-w2`（5-window 并行方案 A 新建；主 wt 借给 W4 conduct batch1）

### 环境备注

本 R1 在独立 **W2 worktree** 执行，非主 wt。起因: 前序 session 把 W1 card renames + W2 knowledgeTree.js 打包 stash 为 `stash@{0}: pre-w4-orphan-from-prev-session` 污染主 wt index。方案 A 新建 `/home/ops/projects/edu-cloud-w2` worktree + `git checkout stash@{0}[^3] -- <W2 6 文件>` selective 提取，零 W1 污染。node_modules 通过 symlink 到主 wt 共享（只读使用）。

**L015 自揭**: T11 首次 commit attempt 因 `git add CLAUDE.md && ... git commit` 在 logging-guard 拦截时 `&&` 链整条未执行，CLAUDE.md 未 staged 但 commit message 误称含 CLAUDE.md（仅 6 files committed）→ 独立 `191a169` 补 commit 平账。T12 commit staging 核验后 4 files（含 CLAUDE.md）一次到位。

### 逐 Task 自审

| Task / Step | 计划要求（plan 3170-3534） | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T11 Step 1: api/knowledgeTree.js 新增 getExamItems + getStatsOverview | `async function + return resp.data` | 按 plan 示例精确追加；保留既有 4 函数 `() => client.get()` 风格 | 🔀 | 新 2 函数 unwrapped data（消费方 ExamItemsTab 直接 `data.items/data.total`），既有 4 函数返回 AxiosResponse；风格分裂但符合 plan R6 锁定 contract |
| T11 Step 2: ExamItemsTab.vue | plan 示例含 `item.difficulty` + UI "难度 X/5" + `console.error` | `item.score` + UI "分值 X 分"；删 console.error | 🔀×3 | (a) `score` 替 `difficulty`（handoff 前置接口契约 + T8 R2 schema 锁定：assessment_items 无 difficulty 列，score 为分值）；(b) UI 标签随字段改，无 /5 分母；(c) 删 plan 示例 console.error 满足 logging-guard 硬拦截，catch 仍重置 `items=[], total=0`（UX 等价，失去 debug trace）|
| T11 Step 3: StudyUnitTab.vue | plan 示例 `\|\|` | `??`（nullish coalescing）| 🔀 | 规划权重 0 值语义保留（考频 0 有意义非"无数据"；`\|\|` 会把 0 显为 '—'）|
| T11 Step 4: NodeDetailDrawer 追加 2 tab | F007: 仅追加不移除原 5 tab；顶部 n-descriptions + 编辑表单不动 | template 在 `<n-tab-pane name="questions">` 后插入 2 n-tab-pane；script 追加 2 import；原 5 tab + n-descriptions + `<template v-if="canEdit">` 编辑表单 **0 字节修改** | ✅ | `git diff f2e9ba9^..f2e9ba9 -- NodeDetailDrawer.vue` 净 +8 行（template +6 / script +2），0 删除行 |
| T11 Step 5: ExamItemsTab.test.js + StudyUnitTab.test.js | 3 + 2 = 5 tests | 严格按 plan 示例；相对路径 `../../components/knowledge-tree/<x>.vue`（对齐既有 `useKnowledgeTree.test.js` 风格，非 `@/` alias）| ✅ | 5 PASS |
| T11 Step 6-7: vitest + commit | 5 PASS + commit | knowledge-tree 子集 13 files / 144 tests PASS（5 新 + 139 既有）零回归；commits f2e9ba9 + 191a169 | ✅ | |
| T12 Step 1: buildChapterTree 纯函数 append to useKnowledgeTree.js | BOOK_LABELS / bookMap / sort by id | 严格按 plan 示例（仅格式注释精简） | ✅ | |
| T12 Step 2: TreeNavPanel 内部 navMode + chapterTreeData | plan 示例简化 template（删 nav-header slot / weakConcepts / renderSuffix）；handleSelect 重命名 onSelect | 完整保留现有 TreeNavPanel 所有元素（nav-header slot / searchQuery / expandedKeys / selectedKeys / manualExpandedKeys watch / renderSuffix / weakConcepts / reviewStatusIcons / masteryColor）+ 追加 navMode radio / chapterTreeData / handleSelect 早退 + defineExpose | 🔀×5 | (a) handleSelect 保留现名（避免跨文件 refactor 外溢）；(b) 章节模式 n-tree 不传 selectedKeys/expandedKeys（module 特化属性不适用 book:/chapter:/section: key 空间）；(c) `defineExpose({ navMode, handleSelect })` 最小 public surface 供测试入口（plan 示例未写）；(d) 保留 `!key.startsWith('BC_')` 过滤（plan 示例删）；(e) handleSelect 追加 `if (key.includes(':')) return` 早退聚合节点 |
| T12 Step 3: TreeNavPanel.test.js | 3 + 4 = 7 tests | 3 buildChapterTree + 6 TreeNavPanel = **9 tests** | 🔀 | 新增 2 反证断言：(5) 切 chapter 模式后 select-node 仍带完整 node（F010 跨模式持续）；(6) book:/chapter:/section: 聚合 key handleSelect 不 emit（防误识 concept）|
| T12 Step 4-5: vitest + commit | 7 PASS + commit | TreeNavPanel 子集 9 PASS；knowledge-tree 子集 14 files / 153 tests PASS 零回归；commit 5607a9a | ✅ | |

> 状态：✅一致 / ❌不一致 / 🔀改进（plan vs 实际偏离）

### 3 陷阱规避证据（batch3a 教训映射）

| 陷阱 | 规避证据 |
|------|---------|
| **F001（composable 已导出 ref 时页面禁新建本地 ref）** | T12 改 `useKnowledgeTree.js` 前先审完整 `return {}` 清单（line 78-83：`navigationData, graphData, masteryData, qualityIssues, qualitySummary, modulesQuality, loading, selectedModule, selectedStudentId, moduleMastery, nodesWithMastery, ...`），确认 `selectedStudentId` 已导出且本 Task 不需新建。`buildChapterTree` 作为**模块级命名导出**（非 composable return），与 `useKnowledgeTree()` 内部 ref 无状态耦合。T11 NodeDetailDrawer 新增 tab 不新建任何 ref，tab 组件消费 `props.node.id / props.node.study_unit_id` 等既有字段 |
| **F002（mount.test.js stub 吞新 prop）** | NodeDetailDrawer 对外 **props/emit 契约不变**（仍 `show/node/canEdit` + `close/edit`），仅 n-tabs 内部新增 tab-pane → `KnowledgeTreePage.mount.test.js:218-220` NodeDetailDrawer stub `props: ['show', 'node', 'canEdit']` 无需升级。grep 验证：`f2e9ba9` diff 6 文件无 mount.test.js。TreeNavPanel 同理（F002 硬约束 props/emit 不变）→ 即便 mount.test.js stub TreeNavPanel，亦无需升级 |
| **F003（mock 缺关键 API spy 导致 watch 路径零覆盖）** | TreeNavPanel.test.js 不依赖 G6（TreeNavPanel 无 G6 渲染）；n-tree 用 naive-ui 真实组件非 stub。mutant：删 `navMode === 'module'` 分支 → module 断言 `.not.toContain('必修1')` fail；删 `.includes(':') return` → 聚合 key 走到 nodeMap 查找 undefined → 本 test fixture 偶然不 emit（test 仍 PASS）。**已在"未覆盖瑕疵"段 pre-declare** |

### 预审自检（14 新断言 = T11 5 + T12 9）

| 断言 slice | 文件 | 反证（mutant 操作 → 预期 fail） |
|-----------|------|-------------------------------|
| ExamItemsTab 空态（total=0）| ExamItemsTab.test.js | 删 `v-else-if="total === 0"` → "暂无关联高考真题"不显 → fail |
| ExamItemsTab 渲染 items + formatExamId | ExamItemsTab.test.js | 删 `{{ item.stem }}` → "光合作用相关题干"不现 → fail；删 `formatExamId` regex 分支 → "2019 ZJ" 不现 → fail |
| ExamItemsTab 首屏调 getExamItems('Z',1,10) | ExamItemsTab.test.js | 删 `watch(props.nodeId, ..., { immediate: true })` → getExamItems 未被调用 → fail |
| StudyUnitTab 空态 | StudyUnitTab.test.js | 删 `v-if="!node.study_unit_id"` → 空态不显 → fail |
| StudyUnitTab 完整字段 | StudyUnitTab.test.js | 删任一 field-row → 对应字符串 fail (70 分钟/8.5/第3章/su:bio_sr:m1_test) |
| buildChapterTree 三级聚合 | TreeNavPanel.test.js | 删 `new Map()` 初始化 → chapters undefined → 构造抛错 → fail |
| buildChapterTree 跨册（2 books） | TreeNavPanel.test.js | 删外层 `Array.from(bookMap.values())` → 返回 undefined → `tree.length` TypeError → fail |
| buildChapterTree 空 chapters | TreeNavPanel.test.js | 删 `\|\| []` 守卫 → null.forEach 抛错 → fail |
| TreeNavPanel 默认 module 模式 | TreeNavPanel.test.js | 改 `ref('chapter')` → `.not.toContain('必修1')` fail（出现"必修1"）|
| TreeNavPanel 切 chapter 显"必修1" | TreeNavPanel.test.js | 删 `<n-tree v-else :data="chapterTreeData">` → chapter 模式无 tree → `.toContain('必修1')` fail |
| select-module emit 'M1' string | TreeNavPanel.test.js | 改 `emit('select-module', keys[0])` → `emit(..., keys)` → `toEqual(['M1'])` fail（传入 array）|
| select-node 完整 node（F010 module 模式）| TreeNavPanel.test.js | 改 `emit('select-node', node)` → `emit(..., keys[0])` → `typeof payload === 'object'` fail |
| select-node 完整 node（F010 chapter 模式持续）| TreeNavPanel.test.js | 同上，且覆盖 navMode='chapter' 下的 nodeMap 查找路径 |
| 聚合 key book:/chapter:/section: 不 emit | TreeNavPanel.test.js | 删 `if (key.includes(':')) return` → book:b1 走到 `['M1'..'M5'].includes`=false → 落到 `nodeMap.value['book:b1']`=undefined → 偶然不 emit（PASS）。**本断言防御层次低**，见"未覆盖瑕疵"段 |

### 契约保持自检

**T11 F007（追加而非替换）**: `NodeDetailDrawer.vue` 净 diff +8 行（0 删除）。原 5 tab（curriculum/textbook/das/evidence/questions）+ 顶部 n-descriptions + `<template v-if="canEdit">` 编辑表单字节级未动。grep `<n-tab-pane` 前后数量 5→7，差 2（新 exam_items + study_unit）。

**T12 F002（TreeNavPanel props/emit 不变）**:
- props 签名: `{ navigation: Array, moduleMastery: Array, nodesWithMastery: Array, selectedModule: String }` — 类型/默认值/列表全保留
- emits: `['select-module', 'select-node']` — 未新增，未改 payload 类型
- `KnowledgeTreePage.vue:13` 调用方未触（本卡 scope 严禁）

**T12 F010（select-node payload 完整 node 对象）**:
- `handleSelect` 叶子分支: `const node = nodeMap.value[key]; if (node) emit('select-node', node)` —— 完整 node（含 mastery/module/textbook_chapters/review_status 等）
- 测试 F010 module + chapter 模式分别触发 → payload.id/name/module 精确断言

### Scope 验证

```
$ git diff master..HEAD --name-only  # w2 worktree, HEAD = 5607a9a
CLAUDE.md
frontend/src/__tests__/knowledge-tree/ExamItemsTab.test.js
frontend/src/__tests__/knowledge-tree/StudyUnitTab.test.js
frontend/src/__tests__/knowledge-tree/TreeNavPanel.test.js
frontend/src/api/knowledgeTree.js
frontend/src/components/knowledge-tree/ExamItemsTab.vue
frontend/src/components/knowledge-tree/NodeDetailDrawer.vue
frontend/src/components/knowledge-tree/StudyUnitTab.vue
frontend/src/components/knowledge-tree/TreeNavPanel.vue
frontend/src/components/knowledge-tree/useKnowledgeTree.js
```

10 文件全命中 handoff 白名单（7 组件+API+测试 + CLAUDE.md + TreeNavPanel.test.js）。W1 `card/*` / W3 `frontend-nuxt/*` / W4 `conduct/*` 范围零触及。**测试路径修正**: 本卡 §2.1 笔误 `components/knowledge-tree/__tests__/*`（R5-T002 已标缺陷），按前序 handoff 白名单 + `ls` 实证 `frontend/src/__tests__/knowledge-tree/` 为权威路径。

### 验证清单自检

- ✅ T11 NodeDetailDrawer 追加 2 n-tab-pane 净 diff +8 行 0 删除（F007），原 5 tab + 顶部 n-descriptions + `<template v-if="canEdit">` 编辑表单字节级未动
- ✅ T11 ExamItemsTab 按 T8 R2 schema 用 `item.score`（不用 plan 示例 difficulty），UI "分值 X 分"；删 plan 示例 `console.error` 满足 logging-guard，catch 仍重置 items=[]/total=0（UX 等价）
- ✅ T11 StudyUnitTab 用 `??` 保留 0 值语义（考频/易错度 0 为有效值非"无数据"）
- ✅ T12 useKnowledgeTree return 清单先审后改（规避陷阱 F001），`buildChapterTree` 作**模块级命名导出**不进 composable return
- ✅ T12 TreeNavPanel props/emit 契约不变（F002：4 props + 2 emits 签名 + 默认值 + 类型全保留）
- ✅ T12 select-node 仍 emit 完整 node 对象（F010，模块模式 + 章节模式均测试覆盖；diff 核验 `handleSelect` 叶子分支走 `nodeMap.value[key]`）
- ✅ T11+T12 未触 `KnowledgeTreePage.vue` / `KnowledgeTreePage.mount.test.js`（F002 mount stub 无需升级，对外契约不变）
- ✅ T11+T12 未触 `ConceptMapPanel.vue` / `ColorModeToggle.vue` / `heatmapUtils.js`（batch 3.a 产物零回归）
- ✅ knowledge-tree 子集回归 14 files / 153 tests PASS（T11 基线 13/144 → +3 files / +9 tests，零 fail）
- ✅ Git staging 纯净: `git diff master..HEAD --name-only` 10 文件全在 handoff 白名单；W1 card / W3 haofenshu / W4 conduct 范围零触及
- ✅ Worktree 隔离: `/home/ops/projects/edu-cloud-w2` 独立 w2 worktree，主 wt（W4）与本 R1 零相互污染
- ⚠️ buildChapterTree dedupe 分支反证弱 + 聚合 key 不 emit 反证偶然 — 已在"未覆盖瑕疵"段 pre-declare
- ⚠️ 全前端 vitest 未跑（仅 knowledge-tree 子集 14/153）— 其他模块理论零触及但未实证，建议 Reviewer 执行 `npx vitest run` 全量
- ⚠️ T11 commit message L015 虚报 CLAUDE.md → 独立 `191a169` 补 commit 平账 + 本交接单"环境备注"段自揭

### 🔀 偏离汇总（审查关注点）

1. **api/knowledgeTree.js 风格分裂**: 新 2 函数 unwrapped vs 既有 AxiosResponse — plan R6 锁定，下游消费者按 plan 契约，不违反
2. **ExamItem.score 替 difficulty + UI 标签改**: handoff 前置接口契约明文（T8 R2 schema 锁定）
3. **`??` vs `||`**: 0 值语义保留
4. **删 plan 示例 console.error**: logging-guard 硬拦截；UX 等价（catch 状态重置保留，失去 debug trace）—— 边缘 `behavior_change` 标签可讨论
5. **handleSelect 保留现名**: 避免跨文件 refactor 外溢
6. **defineExpose 新增**: Vue 3 script setup 默认私有，expose 为最小 public surface 供 `wrapper.vm` 测试入口；`behavior_change=false`（测试才访问，生产代码不使用）
7. **TreeNavPanel BC_ 过滤 + 聚合 key 早退**: 保留 + 追加，防御双层
8. **章节模式 n-tree 不传 selectedKeys/expandedKeys**: module 特化属性 key 空间不重叠（M1..M5 vs book:/chapter:/section:），用 NTree 默认
9. **CLAUDE.md KnowledgeTreePage 行累加 2 句**: T11（191a169）+ T12（5607a9a）= 2 句描述。handoff "不动 CLAUDE.md / Batch 3 完整收口时再说" 的大改延后到 3.c；当前为 doc-sync-guard 硬拦下的最小合规追加
10. **测试路径以前序 handoff 为权威**: 本卡 §2.1 笔误已规避

### 基线数据

| 指标 | Batch 3.a R2（2026-04-14 10:04）| Batch 3.b R1 (2026-04-17 22:33)|
|------|-----------|---------|
| knowledge-tree files | 11 | **14 (+3)** |
| knowledge-tree tests | 139 | **153 (+14)**（T11 +5 / T12 +9）|
| 全前端 vitest | 24 files / 233 tests | 27 files / 247 tests（预期）|

全前端回归命令: `cd /home/ops/projects/edu-cloud-w2/frontend && npx vitest run`（本交接单写作时**只跑 knowledge-tree 子集**；建议 Reviewer 跑全量验证全前端零回归）。

### 自查（四要素）

**边界: ExamItem.options 为 raw JSON string** — ExamItemsTab.vue 不渲染 options（保持 plan 示例），不 JSON.parse。下游若需展开选项，scope 外，R2 可补。

**异常: buildChapterTree null chapters** — `const chapters = node.textbook_chapters || []` 守卫；空数组 test 覆盖；tree length=0。

**字符串匹配: BOOK_LABELS['b1'] = '必修1 分子与细胞' 与 M1.name '分子与细胞' 重叠** — `.not.toContain('必修1')` 精确区分 module 模式（仅"分子与细胞"）；反证"默认 chapter 模式" → 顶层出现"必修1" → fail，mutant 有效。

### 送审准备

1. Baseline 对齐: knowledge-tree 子集 14 files / 153 tests PASS
2. Commits: `f2e9ba9` (T11) → `191a169` (T11 CLAUDE.md 补) → `5607a9a` (T12)
3. Staged 纯净: 每次 commit 前 `git diff --cached --name-only` 严格验证白名单；L015 自揭段已说明 T11 首 commit 虚报已补
4. Worktree w2 独立，零主 wt 污染
5. 反证矩阵 14 条上表列；未逐条实测粘贴 fail 输出（R1 结构可省，Reviewer 如要求补 slice 请指定）
6. 下一步: `codex-review` skill 进行 Batch 3.b R1 GPT 独立审查（subject_ref `commit:f2e9ba9..5607a9a`）

### 未覆盖瑕疵（pre-declare，Reviewer 可直接判 R1→R2 finding）

1. **buildChapterTree dedupe 分支反证弱**: 当前 fixture 每 node 仅 1 chapter，`section.concept_ids.includes` dedup check 未被显式覆盖（mutant 删 `.includes` check → 测试仍 PASS）。补救：R2 补 "同 node 出现 2 次同 section" fixture。
2. **聚合 key 不 emit 反证偶然**: 删 `if (key.includes(':')) return` 后，book:b1 走到 nodeMap 查找为 undefined，偶然不 emit（test PASS）。更严格反证需构造 nodeMap 有 book:b1 的对抗 fixture。补救：R2 调整断言 — 直接断 handleSelect 早退（覆盖"意图"而非"副作用"）。
3. **测试文件缺 logger import（logging-guard 💡 建议级）**: hook 排除规则 `tests?/` 未命中 `__tests__/` 目录（hook 算法小缺陷），测试文件无需 logger。不影响 commit。
4. **T11 commit message L015**: `f2e9ba9` commit message 声称含 CLAUDE.md 但不含，`191a169` 补 commit 平账 + 本交接单自揭段详述。historical 痕迹保留。
5. **全前端 vitest 未跑**: 仅跑 knowledge-tree 子集 14/153。其他模块（conduct/ analytics/ parent/ paper/shell/ studio/ ai/ ...）理论零触及但未实证全绿。建议 Reviewer 执行 `npx vitest run` 全量 1 次。

---

status: submit-for-review
