---
type: handoff
created: 2026-04-14 06:20:00
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-knowledge-graph-optimization-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-plan.md
state: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-state.json
gates: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-gates.json
prev_handoff: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-handoff-batch3.md
batch: 3.a
batch_scope: T9-T10（heatmapUtils + ColorModeToggle + ConceptMapPanel 节点视觉升级）
---

# 约束与偏好（design.md / plan.md 未记录的增量信息）

## Tier 与流程

**T3 流程**（2 窗口）。本次是 Batch 3.a 子批执行：Executor 新会话 → 执行 T9-T10 → 审查交接单 → Planner 触发 codex-review (Gate 2 code_review_batch3a)。

**Batch 3 拆成 3 子批**（Planner 决策，用户批准）:
- **3.a** (本次): T9 + T10 — heatmap util + 视觉升级（强耦合：T10 消费 T9 工具）
- 3.b: T11 + T12 — NodeDetailDrawer tab + 章节导航（独立组件）
- 3.c: T13 + T14 — ModuleOverviewPanel + Phase 1 收尾 + **P001 处置**（INV-002 L1 集合相等测试 + INV-004 前端契约映射）

本 Executor **禁止越界**实现 T11-T14 任何内容。

## 3.a 范围精确化（scope_guard 硬拦截依据）

**允许 commit 的文件清单**（T9-T10 plan 声明）:

| 文件 | 操作 | Task | 说明 |
|------|------|------|------|
| `frontend/src/components/knowledge-tree/heatmapUtils.js` | CREATE | T9 | 新 util，log 尺度 heatmapColor + masteryColor + reviewStatusColor + nodeSizeFromImportance |
| `frontend/src/components/knowledge-tree/ColorModeToggle.vue` | CREATE | T9 | 新组件，n-radio-group 三模式切换 |
| `frontend/src/__tests__/knowledge-tree/heatmapUtils.test.js` | CREATE | T9 | 新测试，~10 断言（含 clamp / log scale / mastery R>G / monotonic size） |
| `frontend/src/__tests__/knowledge-tree/ColorModeToggle.test.js` | CREATE | T9 | 新测试 |
| `frontend/src/components/knowledge-tree/ConceptMapPanel.vue` | MODIFY | T10 | 接收 colorMode prop + buildG6Data 视觉分支 + watch colorMode 重绘 + defineExpose({buildG6Data}) |
| `frontend/src/pages/KnowledgeTreePage.vue` | MODIFY | T10 | 挂 ColorModeToggle + 传 color-mode prop + watch selectedStudentId 自动切模式 |
| `frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js` | MODIFY | T10 | 新增 3 个 buildG6Data 行为断言测试（size 反映 importance / colorMode 改 fill / mastery R>G） |

**严禁修改**：NodeDetailDrawer / ModuleOverviewPanel / TreeNavPanel / useKnowledgeTree.js / api/knowledgeTree.js — 全部留给 3.b/3.c。

Commit 前必跑 `git diff --cached --name-only` 确认只含上述 7 个文件。超范围 → `git reset HEAD <file>` 精确剔除再 commit。

## 前置依赖（T7/T8 已交付的 v3 字段，不要重新实现）

### Graph API v3 返回字段（Task 7 已交付，ConceptMapPanel 已消费大部分）

`GET /api/v1/knowledge-tree/graph?module=M1` 返回的每个 node 含：

| 字段 | 类型 | 语义 | T10 消费点 |
|------|------|------|-----------|
| `exam_frequency` | int, default 0 | 高考题频次，max≈1313, median≈11 偏斜分布 | heatmapColor 入参（**必须 log 尺度**） |
| `exam_coverage` | float 0-1 | 覆盖率 | 暂不消费（T13） |
| `avg_difficulty` | **float \| None** | **None 语义保留**：零考频概念无代理值 | T10 若用它着色 → 必须 null fallback |
| `importance_score` | float 0-10 | 归一化（INV-005 R2 单调性锁定） | `nodeSizeFromImportance(score)` 入参 |
| `textbook_chapters` | list | 结构 `[{book, chapter, section, title}]` | 不消费（T12/T13） |
| `study_unit_id` | str \| None | 多数为 None | 不消费（T11） |
| `estimated_minutes` | int \| None | 多数为 None | 不消费（T11） |
| `prerequisite_depth` | int, default 0 | 前置深度 | 不消费 |
| `planning_weight` | **dict \| None** | **MCU 映射覆盖率 ~24/108**，多数 None | 不消费（T11） |
| `review_status` | str | `ai_draft` / `teacher_reviewed` / `published` | reviewStatusColor 入参 |

### ConceptMapPanel 已有行为（Phase 2/2.5，不要重写）

- `focusedNodeId` 内部 ref（焦点模式，点击节点后其他淡化）
- `buildVisibleEdgeList` helper + `relatedNodeIds/relatedEdgeIds` computed
- G6 `node.state.faded` / `edge.state.dimmed·emphasized` + `updateElementStates`
- `createGraph` 末尾**焦点重放**（watch colorMode 重绘后必须保留，plan T10 Step 1 watch 内已写 `if (focusedNodeId.value) updateElementStates(focusedNodeId.value)`）
- G6 Tooltip plugin 徽标悬停（跨模块 peer 列表）

**回归守门**：T10 新增 watch colorMode 触发 `setData + render` 后必须保留 focusedNodeId 状态，否则会破坏 Phase 2.5 已落盘的焦点模式。plan 已要求，Executor 不得省略。

## 测试基线与风格约束

### Baseline（本 handoff 前跑过）

- 后端 pytest: 1851 passed + conduct 106（R3 PASS 基线）
- 前端 Vitest: **22 files / 200 passed**（2026-04-14 06:14 跑过）
- **Vitest 含大量 pre-existing AppSidebar router-link resolve 警告**——是 pre-existing Vue warn，不阻断，Executor 无需处理

### 精确断言原则（Batch 2 R1/R2/R3 审查强制，3.a 必须延续）

**禁用弱断言**:
- `expect(x).toBeTruthy()` / `expect(x).toBeGreaterThan(0)` / `expect(status).toBeOneOf([200, 404])`
- `if (result) { ... }` / `assert result`

**必须精确**:
- `expect(setA).toEqual(new Set([...]))` / `expect(color).toMatch(/^#[0-9a-f]{6}$/i)` / `expect(size).toBeGreaterThanOrEqual(50)` 且 `.toBeLessThanOrEqual(70)`
- 数值断言必须上下界都锁定

### 反证风格（R2 加固，3.a 必填）

每个 T9 测试契约 slice 必须有"错误实现会怎样失败"的反证说明。plan 测试契约已列：
- heatmapColor 反例: "线性映射在 freq 分布偏斜时区分度极差" → 测试 `c1 !== c100 !== c1000`，log 尺度下三者差异显著；线性实现（freq/max）会让 freq=100 和 freq=1000 颜色几乎相同
- masteryColor 反例: "weak 应为红色系（R > G）" → 若走错分支返回绿色（solid）会 fail
- nodeSizeFromImportance 反例: "monotonic increasing" → 若硬编码常量，`size(5) > size(2)` fail

**mutant 视角**：每写完一个测试，自问"如果删除被测函数核心逻辑，此测试会 fail 吗"。不会 → test-gap HIGH。

### mount 测试陷阱（T10 特有）

`ConceptMapPanel` 在 happy-dom 下 **G6 canvas 会报错**（plan 已规避：测试不调 `g6Graph.render()`，只断言 `buildG6Data()` 返回值）。

Executor 必须用 `defineExpose({ buildG6Data })` 暴露工具函数给测试，不要尝试验证 G6 实际渲染（TD-001 test_debt 已接受）。plan Line 2679 明确要求。

## 前端技术栈（本次不引新依赖）

- Vue 3.5 Composition API + Naive UI 2.44 + Vite 7（现有）
- Vitest 4 + happy-dom + @vue/test-utils（现有）
- AntV G6（ConceptMapPanel 已在用）
- **禁止**引入 d3/chroma/color-js 等颜色库 — plan Line 76 已明确，heatmapColor 用纯 JS 手算 RGB 插值

## 环境与流程约束

- **前端启动端口**: 5273（Vite dev），后端 9000。Vite 代理 `/api` → `http://localhost:9000`。不要硬编码 localhost
- **Windows bash Vitest 路径**: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run <文件名>`
- **port_guard**: 启动前端 dev server 用 `python ~/.claude/scripts/serve.py "C:/Program Files/nodejs/npm.cmd" run dev`，不要直接 `npm run dev`
- **LF/CRLF 警告**：Windows git 会警告，忽略
- **doc_sync_guard**：T9 新增 `heatmapUtils.js` / `ColorModeToggle.vue` 组件 → **不需要**同步 `edu-cloud/CLAUDE.md`（组件是私有子组件，不在公共 API 端点/页面段范围）。T10 修改 ConceptMapPanel 也不涉及 CLAUDE.md 条目。
- **scope_guard**: 本次 commit 只能含上述 7 个文件，禁止其他任何 .claude/、docs/plans/ 以外内容

## Batch 2 踩过的坑（继承避免）

1. **staging 污染**：其他并行会话可能 `git add .` 污染 index。**commit 前必跑 `git diff --cached --name-only` 确认纯净**
2. **Batch 2 f70af8d 教训**：specific path add 后 commit，若此前 staging 已含外部文件会全部 commit → 用 `git reset HEAD` 清 staging，然后 `git add <具体文件>`

## 审查约束

- **Gate 2 最多 3 轮**（code_review_batch3a）
- **🔀 偏离标注**：若实现偏离 plan（颜色值、size 上下界、UI 细节），审查交接单逐 Task 自审表必标 🔀 + 具体变更
- **behavior_change 单独确认**：GPT 若将颜色阈值 / 节点 size 上下界视为 behavior_change finding，Executor 不得自行同意，必须回传 Planner 确认
- **审查交接单路径**: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-review-handoff-batch3a.md`，写完 `git commit -m "review: kg-phase1 batch 3.a 审查交接单"`

---

# 启动 Prompt（复制到新窗口）

```
[edu-cloud] Executor | 2026-04-14 06:20:00
项目目录: C:\Users\Administrator\edu-cloud
Tier: T3 / Batch 3.a

读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-handoff-batch3a.md
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-plan.md（T9-T10 段，lines 2271-2782）

范围锁定：仅 Task 9 (heatmapUtils + ColorModeToggle) + Task 10 (ConceptMapPanel 节点视觉升级)。禁止越界实现 T11-T14 任何内容。

使用 executing-plans skill 执行。按 plan T9 Step 1-6 + T10 Step 1-6 顺序推进：
- T9: 先写 heatmapUtils 测试（TDD Red）→ 实现 heatmapUtils.js → 写 ColorModeToggle 测试 → 实现 ColorModeToggle.vue → npx vitest run 验证 → commit
- T10: 修改 ConceptMapPanel.vue（接 colorMode prop + buildG6Data 三分支 + watch colorMode + defineExpose buildG6Data）→ 修改 KnowledgeTreePage.vue 挂 ColorModeToggle + watch selectedStudentId → 新增 3 个行为断言测试 → npx vitest run → 启动前端本地验证（浏览器看节点大小差异/颜色切换/焦点模式回归）→ commit

关键约束（详见 handoff-batch3a）：
- 禁止引入 d3/chroma 等新颜色库（纯 JS 手算 RGB 插值）
- heatmapColor 必须 log 尺度（freq 偏斜分布，max≈1313 median≈11）
- buildG6Data 必须通过 defineExpose 暴露给测试
- watch colorMode 重绘后必须保留 focusedNodeId 状态（Phase 2.5 焦点模式回归）
- 测试精确断言 + 反证风格（禁弱断言）
- mastery='weak' 断言 R>G，非硬编码颜色
- scope_guard: commit 前 `git diff --cached --name-only` 确认 7 文件范围，严禁其他修改
- 前端启动走 `python ~/.claude/scripts/serve.py "C:/Program Files/nodejs/npm.cmd" run dev`

测试基线：前端 Vitest 22 files / 200 tests 全绿（2026-04-14 06:14）。3.a 完成后期望 ~210 tests 全绿。

完成后输出审查交接单：
- 路径: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-review-handoff-batch3a.md
- 格式按 ~/.claude/rules-t3/review-templates.md「审查交接单」段（含逐 Task 自审表 / 预审自检表 / 验证清单自检 / 自查四要素）
- 自审表「状态」列必填（✅/❌/🔀），🔀 必写具体变更内容
- 预审自检表每行必含反证验证列（删除核心逻辑后测试是否 fail）
- 写完 `git add <路径> && git commit -m "review: kg-phase1 batch 3.a 审查交接单"`

使用 codex-review skill 进行 GPT 代码审查。
```
