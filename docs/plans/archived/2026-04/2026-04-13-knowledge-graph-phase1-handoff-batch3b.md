---
type: handoff
created: 2026-04-14 09:15:00
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-knowledge-graph-optimization-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-plan.md
state: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-state.json
gates: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-gates.json
prev_handoff: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-handoff-batch3a-r2.md
batch: 3.b
batch_scope: T11 (NodeDetailDrawer 高考真题+学习单元 tab) + T12 (教材章节导航模式)
---

# 约束与偏好（design.md / plan.md 未记录的增量信息）

## Tier 与流程

**T3 流程**（2 窗口）。Batch 3.b 子批执行：Executor 新会话 → T11 + T12 → 审查交接单 → codex-review Gate 2 (`code_review_batch3b`)。

**Gate 2 最多 3 轮**。Batch 3.a 参照：R1 FAIL → R2 PASS（1 次迭代即闭环）。

## 已完成进度快照（2026-04-14 09:15）

| 阶段 | 状态 | Gate 证据 |
|------|------|---------|
| Plan Review | ✅ R6 PASS | `plan_review=pass`, subject_hash `a963e85b`（R6 修订含 T9-T13 测试路径校正） |
| Batch 1 (T1-T6) | ✅ R2 PASS | `code_review_batch1=pass`, `1c3c1a2..bcb1971` |
| Batch 2 (T7-T8) | ✅ R3 PASS | `code_review_batch2=pass`, `d300263` |
| Batch 3.a (T9-T10) | ✅ R2 PASS | `code_review_batch3a=pass`, `2ab10a2..c5bff80`（R1 F001/F002/F003 全 resolved-correct） |
| **Batch 3.b (T11-T12)** | ⏸ pending | 本交接卡派发 |
| Batch 3.c (T13-T14) | ⏸ pending | T14 含 P001 处置 + Phase 1 收尾 |

## Batch 3.a 教训（Batch 3.b 必须规避的 3 个陷阱）

### 陷阱 1: composable 已导出 ref 时页面禁止新建本地 ref（F001 教训）

Batch 3.a Executor 在 `KnowledgeTreePage.vue:119` 新建了 `const selectedStudentId = ref(null)`，而 `useKnowledgeTree.js:81` 其实已经导出了同名 ref，导致状态双真源 → mastery 模式在集成层完全不可用。

**规避方式**（Batch 3.b 适用）：
- T12 要修改 `useKnowledgeTree.js` 新增 `buildChapterTree` 函数 — 在动手前**先读 useKnowledgeTree.js 完整 return {...} 导出清单**
- T11 在 `NodeDetailDrawer.vue` 若需新增状态，优先检查 `useKnowledgeTree.js` 是否已有同名 ref，不要重复新建

### 陷阱 2: 页面级 mount.test.js stub 静默吞新 prop（F002 教训）

Batch 3.a 加了 `ConceptMapPanel` 的新 prop `colorMode/nodesWithMastery`，但 `KnowledgeTreePage.mount.test.js:167` 的 stub props 列表未升级，集成层零回归保护。

**规避方式**（Batch 3.b 必查）：
- T11 给 `NodeDetailDrawer` 加 tab 后，检查 `KnowledgeTreePage.mount.test.js` 的 NodeDetailDrawer stub（若存在）是否需要升级 props/emit 列表
- T12 TreeNavPanel 虽然 props/emit 契约不变（plan F002 约束），但若新增对 `useKnowledgeTree.buildChapterTree` 的依赖，检查 mount.test.js 的 useKnowledgeTree mock 是否暴露新函数
- **凡新增页面级接线，mount.test.js 必须升级 stub + 补集成断言，反证"删除接线测试必须 fail"**

### 陷阱 3: G6/测试 mock 无关键 API spy 导致 watch 路径零覆盖（F003 教训）

Batch 3.a R1 的 `ConceptMapPanel.test.js` G6 mock 没定义 `setData`，组件 try/catch 吞了 `setData is not a function`，watch colorMode 重绘路径零测试。

**规避方式**（Batch 3.b 适用）：
- T11 / T12 的新增测试若依赖 G6 / Naive UI / 自定义组件 mock，**先审 mock 是否覆盖了被测代码路径要调用的所有方法/事件**
- mutant 视角：删除被测逻辑，测试是否 fail？不 fail 即 test-gap HIGH

## Batch 3.b Scope 白名单（9 文件，含 1 可选）

| 文件 | 操作 | 对应 Task | 说明 |
|------|------|---------|------|
| `frontend/src/components/knowledge-tree/ExamItemsTab.vue` | CREATE | T11 | Naive UI n-list + 分页，消费 `getExamItems(nodeId, page, pageSize)` |
| `frontend/src/components/knowledge-tree/StudyUnitTab.vue` | CREATE | T11 | 展示 node.study_unit_id / estimated_minutes / planning_weight / textbook_chapters |
| `frontend/src/__tests__/knowledge-tree/ExamItemsTab.test.js` | CREATE | T11 | 空/有数据/分页三场景 + `getExamItems` mock 反证 |
| `frontend/src/__tests__/knowledge-tree/StudyUnitTab.test.js` | CREATE | T11 | study_unit_id=null 空态 + 完整字段渲染 |
| `frontend/src/components/knowledge-tree/NodeDetailDrawer.vue` | MODIFY | T11 | **追加**两个 n-tab-pane（exam_items + study_unit），**不移除**原 5 tab |
| `frontend/src/api/knowledgeTree.js` | MODIFY | T11 | 新增 `getExamItems` + `getStatsOverview` 函数（T13 也会用 `getStatsOverview`） |
| `frontend/src/components/knowledge-tree/TreeNavPanel.vue` | MODIFY | T12 | 双模式切换（模块 / 章节），**严禁**改现有 props/emit 契约 (plan F002) |
| `frontend/src/components/knowledge-tree/useKnowledgeTree.js` | MODIFY | T12 | **追加** `buildChapterTree(nodes)` 纯函数导出。不要修改已有导出的 `selectedStudentId` / `loadMastery` 等 |
| `frontend/src/__tests__/knowledge-tree/TreeNavPanel.test.js` | CREATE | T12 | `buildChapterTree` 纯函数测试 + 4 个 UI 级测试（模式切换 + emits 契约保持 + F010 select-node 传完整 object） |
| **`frontend/src/__tests__/knowledge-tree/KnowledgeTreePage.mount.test.js`** | **可选 MODIFY** | T11 / T12 | **若** T11 的 NodeDetailDrawer 接线或 T12 的 TreeNavPanel 新 useKnowledgeTree 导出需要页面级集成断言，升级对应 stub + 补断言。**如不需要则省略** |

**严禁修改**：`ConceptMapPanel.vue` / `ColorModeToggle.vue` / `heatmapUtils.js` / `KnowledgeTreePage.vue`（Batch 3.a 产物）、其他任何 frontend 非本清单文件、所有后端文件。

## 前置接口契约（T11 消费 T8 后端 API）

`GET /api/v1/knowledge-tree/graph/{node_id}/exam-items?page=1&page_size=10` 响应（T8 R3 已锁定）:

```typescript
ExamItemsResponse = {
  total: int,             // 概念关联的 L1 真题总数（可为 0）
  items: ExamItem[],      // 当前页
  page: int,
  page_size: int,
}

ExamItem = {
  id: string,             // assessment_items.id (e.g. GK_2019_ZJ_04)
  exam_id: string,        // e.g. GK_2019_ZJ
  question_number: int | null,  // ← **int**, 不是 str
  question_type: string,  // single_choice / multiple_choice / non_choice
  stem: string,
  options: string | null, // **raw JSON string**，前端需 JSON.parse()
  answer: string | null,
  explanation: string | null,
  score: number | null,   // ← T8 R2 改为 score，不是 difficulty（真实 schema 无 difficulty 列）
  module_tag: string | null,
}
```

**降级契约**：knowledge.db 不可达 / 概念未知 → `total=0, items=[]`，HTTP 200（非 404/500）。ExamItemsTab 测试必须覆盖空态。

## T11 关键设计点

### NodeDetailDrawer 追加 tab 的契约约束（plan 明确要求）

**F007 决策**：仅**追加**两个新 tab，**不移除**现有的 `evidence` 和 `questions` tab。教师现有的"教材证据"和"典型真题"浏览路径必须保留。现有抽屉顶部 n-descriptions（基本信息）也保留。

### ExamItemsTab 分页 UX

plan T11 Step 2 示例用 `n-pagination`：分页大小默认 10。若改其他大小（比如 20），必须在交接单 🔀 偏离说明。

### StudyUnitTab 字段降级

- `node.study_unit_id === null`：显示"暂无学习单元"
- `planning_weight === null`：不渲染 MCU 权重段（T10 经验：MCU 覆盖率仅 24/108）
- `textbook_chapters === []`：不渲染"教材章节"段

## T12 关键设计点

### `buildChapterTree` 纯函数规格（plan T12 Step 1）

输入：`nodes: Array<{ id, textbook_chapters: Array<{ book, chapter, section, title }> }>`

输出：`Array<{ book: string, chapters: Array<{ chapter: string, sections: Array<{ section: string, title: string, concept_ids: string[] }> }> }>`

**边界条件**（测试必须覆盖）：
- `nodes=[]` → `[]`
- 某节点 `textbook_chapters=[]` → 节点不进入任何 book（不在树里，不抛错）
- 跨册概念（同 concept 出现在多个 book/chapter）→ concept_ids 在多个 section 里分别出现
- 同 section 多概念 → concept_ids 数组聚合去重

### TreeNavPanel 双模式切换（plan F002 契约不变）

**严禁**：
- 改 props 签名（`modules / mastery / currentModule / currentNode` 当前签名）
- 改 emit 签名（`select-module / select-node`）
- select-node emit 传 id（必须传完整 node 对象，**F010 R4 约束**）

**允许**：
- 内部 state 增加 `navMode: 'module' | 'chapter'` + UI toggle
- 新增对 `useKnowledgeTree.buildChapterTree` 的依赖
- 渲染分支（navMode='chapter' 时调 buildChapterTree 生成章节树）

### TreeNavPanel.test.js 新建（R6 verification 映射目标）

plan INV-004 verification 映射的目标测试。必须覆盖：
1. **模式切换**：默认 `module` 模式 / 切换到 `chapter` 模式后渲染章节树
2. **emits 契约保持**：select-module 事件带模块 id / **select-node 事件带完整 node 对象**（F010 反例：若误传 id 则 `payload.name` undefined fail）
3. **buildChapterTree 纯函数**：用 controlled nodes fixture 验证输出结构
4. **模式切换不破坏 emit 契约**：chapter 模式下点节点仍 emit 完整 node

每个测试必须有反证说明（"错误实现会怎样失败"）。

## 测试风格约束（Batch 3.a R1/R2 强化确认）

- **精确断言**：禁 `toBeTruthy() / toBeGreaterThan(0) / toBeOneOf([200, 404])`
- **反证验证**：每个测试必须附"删除被测核心逻辑后测试 fail"的 mutant 说明 + Executor 必须实测粘贴输出到交接单
- **入口级**：测试走 API / 用户可触达入口，不只测内部函数
- **集成接线**：若 mount.test.js 升级，**必须**补反证（删除接线测试必 fail）

## 基线

- 前端 Vitest: **24 files / 233 tests PASS**（Batch 3.a R2 闭环后，2026-04-14 09:15）
- 后端 stats_service: 13 passed
- 后端 knowledge_tree 全量: 160 passed

Batch 3.b 完成后期望：
- 前端 Vitest 新增 ~20 tests（ExamItemsTab ~4 + StudyUnitTab ~3 + TreeNavPanel ~7 + 可能的 mount.test.js 升级 ~3）
- 总数预期 ~253

## 环境 / 流程约束

- **前端启动端口**: 5273（Vite dev），代理 `/api` → `http://localhost:9000`
- **前端启动命令**: `python ~/.claude/scripts/serve.py "C:/Program Files/nodejs/npm.cmd" run dev`（port_guard 要求）
- **Vitest 运行**: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run <文件名>`
- **scope_guard**: commit 前 `git diff --cached --name-only` 确认只含本批次文件
- **doc_sync_guard**: T11/T12 新组件**不触发** `edu-cloud/CLAUDE.md` 同步（组件属私有子组件，不在公共 API 段）
- **staging 污染防护**：其他并行会话可能污染 index。每次 commit 前 `git status` + `git diff --cached --name-only` 必查

## 审查约束

- Gate 2 名称：`code_review_batch3b`
- 审查交接单路径：`C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-review-handoff-batch3b.md`
- **🔀 偏离强制标注**：plan T11 T12 若实现偏离（字段名/分页大小/UI 细节），审查交接单逐 Task 自审表必标 🔀 + 具体变更内容
- **behavior_change 单独确认**：GPT 若将分页大小默认值 / TreeNavPanel 模式切换默认值识别为 behavior_change，Executor 不可自行同意，必须回传 Planner
- **3.b R2 FAIL 容忍**：Gate 2 R1 FAIL 不罕见（Batch 3.a 先例）。FAIL 按 review-templates "FAIL 升级" 分类处置（code-bug/test-gap 必修，design-concern 入 design.md §待处置）

## commit 策略（建议）

plan T11 Step 7 / T12 Step 5 建议每 Task 一次 commit：
- `feat(frontend): T11 NodeDetailDrawer 高考真题+学习单元 tab (kg-phase1 batch 3.b)`
- `feat(frontend): T12 教材章节导航模式 (kg-phase1 batch 3.b)`

若 mount.test.js 升级，合并进 T11 或 T12 commit 均可（一次性过集成断言）。

---

# 启动 Prompt（复制到新窗口）

```
[edu-cloud] Executor | 2026-04-14 09:15:00
项目目录: C:\Users\Administrator\edu-cloud
Tier: T3 / Batch 3.b

读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-handoff-batch3b.md
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-plan.md（T11 段 lines 2783-3169 + T12 段 lines 3170-3536）

范围锁定：仅 Task 11 (ExamItemsTab + StudyUnitTab + NodeDetailDrawer 追加 2 tab + api/knowledgeTree.js 新增函数) + Task 12 (buildChapterTree + TreeNavPanel 双模式)。禁止越界实现 T13/T14。

使用 executing-plans skill 执行。按 plan T11 Step 1-7 + T12 Step 1-5 顺序推进。

3 个陷阱必须规避（Batch 3.a 血泪教训，handoff-batch3b 详述）：
- 陷阱 1 (F001): T12 改 useKnowledgeTree.js 前先读完整 return {} 导出清单，不要重复新建本地 ref
- 陷阱 2 (F002): T11 加 NodeDetailDrawer tab 后检查 KnowledgeTreePage.mount.test.js stub 是否需升级；mount.test.js 若改必须补集成断言 + 反证
- 陷阱 3 (F003): 新增测试若用 mock，先审 mock 覆盖是否完整（mutant 视角：删除被测逻辑测试是否 fail）

Scope 白名单（9 文件，含 1 可选 mount.test.js）：见 handoff-batch3b "Batch 3.b Scope 白名单" 段。严禁修改 ConceptMapPanel.vue / ColorModeToggle.vue / heatmapUtils.js / KnowledgeTreePage.vue。

关键契约：
- ExamItem.question_number=int / options=raw JSON string / score 代替 difficulty (T8 R2 已锁定)
- 降级契约: knowledge.db 不可达 → total=0, HTTP 200
- NodeDetailDrawer 仅追加 exam_items + study_unit 两个 n-tab-pane，不移除现有 5 tab (plan F007)
- TreeNavPanel props/emit 契约不变 (plan F002)，select-node 传完整 node 对象 (plan F010)
- buildChapterTree 纯函数导出到 useKnowledgeTree.js

测试风格：精确断言（禁 toBeTruthy / toBeGreaterThan 0 / toBeOneOf 200|404）+ 反证验证（实测粘贴输出）+ 入口级 + mutant 视角。

基线：前端 Vitest 24 files / 233 tests PASS；后端 stats_service 13 passed (2026-04-14 09:15)。

scope_guard: commit 前 git diff --cached --name-only 确认只含本批次文件。每个 Task 独立 commit 建议。

完成后输出审查交接单到 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-review-handoff-batch3b.md 并 commit。使用 codex-review skill 进行 GPT 代码审查。
```
