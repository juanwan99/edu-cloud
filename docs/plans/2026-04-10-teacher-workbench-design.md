# 知识图谱教师工作台 Phase 2 设计

> 创建：2026-04-10 18:26:17
> 前置：Phase 1「可信骨架」`docs/plans/2026-04-09-knowledge-graph-model-design.md` [实现完成]
> 辩论基础：`docs/plans/2026-04-09-knowledge-graph-viz-debate.md`
> 状态：设计确认，待计划

> [2026-04-10 20:52:55 实现完成] Commits: 7a5ecfb..549e298 (Batch 1 + Batch 2)
> Batch 1 (T1-T3): 7a5ecfb..8da5228 (GPT R2 PASS)
> Batch 2 (T4-T6): 0cc0819..549e298 (GPT R4 PASS after 3 fix rounds on F-001..F-006)

## §0 背景与动机

Phase 1 完成了知识图谱的数据可信度基础（edge 审核状态机、发布过滤、质量巡检、关系审查工作台）。但右侧图谱视图仍然是 Phase 0 的 G6 力导向图——教师每次打开看到的是抖动的节点和不同的布局，没有空间记忆，违背了辩论共识「不是给人类看的」的改造目标。

Phase 2 把右侧图谱从"AI 自组织的物理模拟"升级为"教师可信赖的固定结构"——按 `prerequisite_hard` 分层、按 `BigConcept` 分带，同一数据输入产生同一视觉输出。

**核心命题：** 用固定的、可预测的布局展示知识结构，让教师形成空间记忆。

## §1 交付物与范围

### 交付物（3 件）

| # | 交付物 | 作用 |
|---|--------|------|
| 1 | **ModuleOverviewPanel**（模块概览） | `module=all` 默认视图，5 个模块卡片 + 跨模块关系摘要 + 审核进度 |
| 2 | **ConceptMapPanel**（骨架概念图） | 按模块展开，分层布局 + BigConcept 背景分带 + 跨模块徽标 + 单击焦点模式 |
| 3 | **ConceptFocusOverlay**（底部焦点面板） | 单击节点后出现，显示分组关系 + 查看详情按钮 |

### 替换关系

```
KnowledgeTreePage
  └── graph-side（右侧）
      ├── 当前：GraphPanel (G6 力导向)         ← 删除
      └── Phase 2：
          ├── 图谱视图 tab
          │   ├── module=all → ModuleOverviewPanel
          │   └── module=Mx  → ConceptMapPanel
          │                     └── 焦点模式 → ConceptFocusOverlay
          └── 审查工作台 tab → RelationReviewPanel（Phase 1 已做）
```

### 不做的事（Phase 2.5+）

- 不做真正的局部子图布局（点击后是轻量高亮，不是独立子视图）
- 不做布局个性化（节点拖拽后不保存位置）
- 不做动画过渡（模块切换是硬切换）
- 不做布局配置 UI（X/Y 间距、band 高度等用代码常量）

### 不改动

- `TreeNavPanel`（左侧树导航）
- `NodeDetailDrawer`（节点详情抽屉）
- `RelationReviewPanel` + 3 个审查子组件（Phase 1 审查工作台）
- 后端 API（Phase 1 Graph API v2 已提供所有所需字段）

## §2 布局算法

### 选择：自定义预计算布局

对 25 节点/模块的规模，采用纯 JS 的 toposort + 坐标分配算法，G6 只作为渲染器（`layout: { type: 'preset' }`，position 由前端直接传入）。

**不选 G6 Dagre 的原因：**
1. Dagre 的 Y 值会被我们的 BigConcept 分带逻辑覆盖，白算一层
2. 两层坐标系互相打架难调试
3. dagreCompound + Combo 增加数据模型复杂度，combo 的视觉与水平分带设计不吻合

**自定义算法的优势：**
1. 对 25 节点规模，~150 行代码足够
2. 完全确定性：同输入→同坐标输出（这是"固定布局"的硬约束）
3. 可以精确对齐 BigConcept band，rank 间距可调

### 算法步骤

```
Step 1: 构建模块内的 hard-DAG（过滤 prerequisite_hard 边，两端都在模块内）
Step 2: Kahn toposort，计算每个节点的 rank
        - 无前置的节点 rank=0
        - 其后继 rank = max(前置 rank) + 1
Step 3: 按 BigConcept 分组节点，确定 band 顺序（按 BigConcept.display_order）
Step 4: 每个 band 分配固定 Y 范围（总高度 / band 数，每条 band 留 16px 间隔）
Step 5: band 内按 rank 排列 X（rank × COLUMN_WIDTH + LEFT_PADDING）
Step 6: 同 rank 多节点时 Y 做微调避免重叠（SIMPLE_JITTER: ±NODE_HEIGHT/2）
Step 7: 缓存 {moduleId → {nodeId → {x, y}}}
```

### 算法边界处理

- **环检测**：Kahn toposort 过程中如果发现环（剩余节点非空但无零入度节点），记录警告并将剩余节点平铺到最大 rank+1 层
- **无前置关系**：如果 band 内所有节点 rank 都相同（无 hard 边），按 display_order 横向均匀分布
- **单节点模块**：直接居中
- **跨 band 的 hard 边**：允许存在，布局算法不特殊处理（由渲染层画直线或曲线）

### 性能预算

| 操作 | 预算 |
|------|------|
| 布局计算（25 节点）| <10ms |
| G6 首次渲染 | <100ms |
| 模块切换感知延迟 | <150ms |
| 缓存命中（同模块二次进入）| 0ms（Vue computed 缓存） |

## §3 ModuleOverviewPanel（模块概览）

当 `selectedModule='all'` 时右侧显示的默认视图。

### 布局示意

```
┌─────────────────────────────────────────────────────────────┐
│  知识图谱 · 全模块概览                         [刷新质量]    │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ M1 分子与细胞 │  │ M2 遗传与进化 │  │ M3 稳态与调节 │       │
│  │ 22 概念      │  │ 24 概念      │  │ 18 概念      │       │
│  │ 3 大概念     │  │ 2 大概念     │  │ 2 大概念     │       │
│  │ 审核 ████░░  │  │ 审核 ██░░░░  │  │ 审核 ░░░░░░  │       │
│  │ 12/22 (55%) │  │ 6/24 (25%)  │  │ 0/18 (0%)   │       │
│  │ ⚠ 3 HIGH     │  │ ⚠ 1 HIGH     │  │              │       │
│  │ ○ 5 MED      │  │ ○ 2 MED      │  │              │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│  ┌──────────────┐  ┌──────────────┐                          │
│  │ M4 生态环境  │  │ M5 生物技术  │                          │
│  └──────────────┘  └──────────────┘                          │
│                                                              │
│  ── 模块间硬前置关系 ──────────────────────────────────────  │
│  M1 → M2  3 条        M1 → M3  5 条        M2 → M3  2 条     │
│  M1 → M4  1 条        M3 → M4  4 条                          │
└─────────────────────────────────────────────────────────────┘
```

### ModuleStatCard 字段

| 字段 | 来源 | 说明 |
|------|------|------|
| 模块名 + 色条 | 常量 | 沿用 MODULE_COLORS |
| 概念数 | `navigation[Mi].big_concepts[].concept_ids.length` 求和 | L1 concept 数 |
| 大概念数 | `navigation[Mi].big_concepts.length` | BigConcept 数 |
| 审核进度 | `teacher_reviewed+published / total` | 节点审核进度条 |
| 质量问题徽章 | `loadQuality(Mi)` 返回的 summary | 只显示 HIGH/MED 计数，LOW 不显示 |
| 点击卡片 | `emit('select-module', Mi)` | 触发 `handleModuleSelect(Mi)` |

### 模块间硬前置关系列表

- 数据来源：遍历 `props.edges`，筛选 `type=prerequisite_hard` 且 source/target 的 module 不同
- 按 `源模块→目标模块` 聚合计数
- 点击条目 → 弹出小面板显示具体关系列表（源概念 → 目标概念）
- 这是附加信息，不是核心交互

### 数据获取

- 复用 `loadGraph('all')` 已加载的数据（nodes + edges）
- 质量徽章数据通过 `loadAllModulesQuality()` 批量拉（5 次并发调用）
- 首次进入页面时自动加载，右上角"刷新质量"按钮重新拉取

## §4 ConceptMapPanel（骨架概念图）

模块内的核心视图。

### 布局示意（M1，3 BigConcept / 22 概念）

```
┌───────────────────────────────────────────────────────────────────────┐
│ ← 返回概览  |  M1 分子与细胞  |  审核 12/22  ⚠ 3 HIGH          [刷新]  │
├───────────────────────────────────────────────────────────────────────┤
│ ┌─ 细胞的分子组成 ─────────────────────────────────────────────────┐  │
│ │   ●水       ●蛋白质 → ●酶         ●核酸            ●糖类        │  │
│ │     \        /            \                        |           │  │
│ │      \      /              \                       ●脂质→M3×2  │  │
│ │       ●无机盐                                                   │  │
│ └─────────────────────────────────────────────────────────────────┘  │
│ ┌─ 细胞的基本结构 ────────────────────────────────────────────────┐  │
│ │   ●细胞学说 → ●细胞膜 → ●跨膜运输 → ●细胞骨架                   │  │
│ │                  \        /                                    │  │
│ │                   ●核糖体  ●线粒体→M3×1                        │  │
│ │                   ●内质网                                      │  │
│ └─────────────────────────────────────────────────────────────────┘  │
│ ┌─ 细胞的生命历程 ─────────────────────────────────────────────────┐  │
│ │   ●细胞周期 → ●有丝分裂 → ●减数分裂→M2×3                        │  │
│ └─────────────────────────────────────────────────────────────────┘  │
│  图例: ●已发布 ●已审 ●草稿  ─硬前置 ┈┈软前置 ┈┈桥接/对比            │
└───────────────────────────────────────────────────────────────────────┘
```

### 视觉规范

| 元素 | 样式 |
|------|------|
| BigConcept 分带 | 淡色背景（模块色 10% 透明度） + 左侧垂直色条 + 顶部标题 |
| 带间距 | 16px 间隔，边界不显示分隔线（避免切碎边） |
| 节点 | 圆形 24-36px，填充/描边按审核状态（复用 Phase 1 配色） |
| 节点标签 | 节点右侧（避免与下层节点文字重叠） |
| 跨模块徽标 | 节点右上角小标签 `→M2×3`，悬停展开对端列表 |
| 硬前置边 | 实线 + 箭头，`rgba(100,116,139,0.6)` |
| 软前置边 | 虚线 + 箭头，浅一级 |
| 桥接/对比边 | 默认隐藏，焦点模式下显示（避免噪声） |

### 头部工具栏

| 元素 | 作用 |
|------|------|
| `← 返回概览` | 触发 `selectedModule='all'`，切回 ModuleOverviewPanel |
| `M1 分子与细胞` | 模块名（只读） |
| `审核 12/22` | 模块内节点审核进度 |
| `⚠ 3 HIGH` | 质量问题徽标，点击跳到 `审查工作台` tab |
| `[刷新]` | 重新拉 graph + quality-check |

### 布局触发与缓存

- `watch` `props.nodes / props.edges / selectedModule` 变化
- 坐标计算在 Vue `computed` 中，自动响应式缓存
- 同模块二次进入 → props 引用不变 → computed 缓存命中

## §5 ConceptFocusOverlay（焦点模式）

单击节点触发的交互模式。

### 视觉变化

**Phase 2 v1（本版本实现）：**
- **选中节点**：完全不透明，描边加粗（+1px 蓝色外环）
- **底部浮动面板**：显示选中概念 + 分组关系 + 操作按钮
- **画布空白点击 / ESC 键**：退出焦点模式

**Phase 2.5 延后项（不在本设计范围）：**
- ~~1 跳邻居完全不透明~~（需 G6 节点 style 动态更新 API，v1 不做）
- ~~其他节点 30% 透明度~~（同上，v1 不做）
- ~~不相关的边 20% 透明度~~（同上）
- ~~相关的边加粗~~（同上）
- ~~桥接/对比边条件显示~~（同上）

v1 通过底部浮动面板提供焦点信息（概念名/描述/关系分组），不在画布上做淡化。淡化视觉效果延后到 Phase 2.5 迭代，理由见 plan.md test_debt。

### 底部浮动面板布局

```
  ┌─────────────────────────────────────────────────────────────┐
  │  蛋白质                            review: teacher_reviewed  │
  │  生物大分子，由氨基酸脱水缩合形成                             │
  │  ──────────────────────────────────────────────────────      │
  │  前置依赖（1）: ← 氨基酸                                      │
  │  后继概念（2）: → 酶, → 核糖体                                │
  │  桥接/对比（0）: 无                                           │
  │  ──────────────────────────────────────────────────────      │
  │  [查看详情]   [标为已审核]   [关闭]                            │
  └─────────────────────────────────────────────────────────────┘
```

- 固定在画布底部，宽度 70%，距底边 16px
- 背景毛玻璃 `rgba(30,30,40,0.85)` + `backdrop-filter: blur(8px)`

### 面板内容

| 区域 | 内容 |
|------|------|
| 头部 | 概念名（大字号）+ review_status 标签 + description（小字号） |
| 分组关系 | 按关系类型分组，每组显示对端概念名（可点击切换焦点） |
| 操作按钮 | `查看详情`（打开 NodeDetailDrawer）/ `标为已审核`（权限检查 canEdit） / `关闭` |

### 退出方式

- 点击画布空白区域（G6 `canvas:click` 事件）
- 按 ESC 键
- 点击底部浮动面板的`关闭`按钮
- 切换模块（自动清除 focusedNodeId）

### 交互细节

- 点击分组列表中的对端概念 → 焦点切换到该概念（不退出焦点模式）
- 跨模块邻居不在列表中（在节点的跨模块徽标里）
- 进入/退出焦点模式不做动画过渡（硬切换）
- 焦点模式状态只存于组件内（`selectedFocusId: ref`），不持久化

## §6 文件结构与变更范围

### 新增文件（7 个）

| 文件 | 职责 |
|------|------|
| `frontend/src/components/knowledge-tree/ModuleOverviewPanel.vue` | 5 模块卡片 + 跨模块关系摘要 |
| `frontend/src/components/knowledge-tree/ConceptMapPanel.vue` | 骨架概念图主组件 |
| `frontend/src/components/knowledge-tree/ConceptFocusOverlay.vue` | 焦点模式底部浮动面板 |
| `frontend/src/components/knowledge-tree/ModuleStatCard.vue` | 单个模块卡片 |
| `frontend/src/components/knowledge-tree/layoutEngine.js` | 纯函数式布局算法 |
| `frontend/src/__tests__/knowledge-tree/layoutEngine.test.js` | 布局算法单元测试 |
| `frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js` | ConceptMapPanel Vitest 测试 |

### 修改文件（2 个）

| 文件 | 变更 |
|------|------|
| `frontend/src/pages/KnowledgeTreePage.vue` | graph-side 按 `selectedModule` 分支：`all` → ModuleOverviewPanel / `Mx` → ConceptMapPanel |
| `frontend/src/components/knowledge-tree/useKnowledgeTree.js` | 新增 `loadAllModulesQuality()` 批量拉 5 模块质量数据 |

### 删除文件（1 个）

| 文件 | 原因 |
|------|------|
| `frontend/src/components/knowledge-tree/GraphPanel.vue` | 替换为 ConceptMapPanel（single-version-discipline） |

### 不引入新依赖

- 复用 `@antv/g6 ^5.1.0`（只用 preset layout + 节点/边渲染 + 内置交互）
- 不引入 dagre / elk / d3-dag（自己写 toposort）
- 不引入新 Naive UI 组件类

### 变更规模

| 类型 | 数量 |
|------|------|
| 新增代码 | ~900 行（Vue 组件 + 布局算法） |
| 删除代码 | ~230 行（GraphPanel.vue） |
| 测试代码 | ~400 行 |
| **净增** | **~1070 行** |

## §7 测试策略

### layoutEngine 单元测试（核心）

| 测试 | 意图 |
|------|------|
| 确定性 | 同一 DAG 输入多次调用返回完全相同的坐标 |
| 空 DAG | 返回空坐标映射，不抛异常 |
| 单节点 | 节点居中 |
| 环形 DAG | 检测到环记录警告，剩余节点平铺到 max rank+1 |
| Band 对齐 | 同 BigConcept 节点 Y 坐标落在对应 band 范围内 |
| Rank 正确性 | 被前置的节点 X 坐标严格大于前置节点 X |
| 同 rank 避让 | 同 rank 同 band 多节点 Y 坐标不相同 |

### 组件测试

| 测试 | 意图 |
|------|------|
| ConceptMapPanel 模块切换 | props.selectedModule 变化时重新渲染 |
| ConceptFocusOverlay 显示 | 点击节点后 overlay 可见 |
| ConceptFocusOverlay 退出 | ESC 键触发关闭 |
| ModuleOverviewPanel 卡片点击 | emit select-module 事件 |
| ModuleOverviewPanel 质量批量加载 | loadAllModulesQuality 调用 |

### 回归测试

- Phase 1 审查工作台（tab 切换、relation review）不受影响
- NodeDetailDrawer 交互不变
- TreeNavPanel 模块选择同步 `selectedModule`

## §8 演进路线图（全景更新）

| Phase | 名称 | 状态 | 核心交付 |
|-------|------|------|---------|
| 1 | 可信骨架 | ✅ 实现完成 | Graph API v2 + 审查工作台 + 巡检 + 发布规则 |
| **2** | **教师工作台（本设计）** | **设计中** | **ModuleOverviewPanel + ConceptMapPanel（分层） + ConceptFocusOverlay** |
| 2.5 | 真正的局部子图 | 待定 | 独立局部路径图布局（如果 Phase 2 高亮方案不够用） |
| 3 | 学习进阶 | 未开始 | sub_concept_progressions schema + 编辑器 + Mastery API v2 |
| 4 | 教学语义 | 未开始 | 误概念层 + 跨学科框架 + 证据联动 |
| 5 | Agent 路径 | 未开始 | StudyUnit 落地 + 路径生成 |
