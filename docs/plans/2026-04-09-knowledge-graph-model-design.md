# 知识图谱多层教学模型 Phase 1「可信骨架」设计

> 创建：2026-04-09 21:12:10
> 辩论基础：`docs/plans/2026-04-09-knowledge-graph-viz-debate.md`（4 轮 Claude×GPT + 外部调研）
> 交接卡：`docs/plans/2026-04-09-knowledge-graph-model-handoff.md`
> 状态：设计确认，待计划
> [2026-04-10 10:27:15 实现完成] Commits: 469350e..7c8dee3

## §待处置

- **KnowledgeTreePage 集成测试缺口** (GPT Batch 2 R2-R3 design-concern): KnowledgeTreePage 的 canEdit watcher 和 handleEdit→loadQuality 逻辑未被页面级挂载测试覆盖。原因：页面组件依赖 authStore + API + AntV G6 + Naive UI，mock 基础设施不存在。已在 composable 层 (useKnowledgeTree.test.js) 和逻辑层 (KnowledgeTreePage.test.js) 独立验证。待项目建立页面级 mock 基础设施后补齐。

## §0 背景与动机

当前知识图谱（108 L1 概念 + 335 关系）全部为 AI 生成草稿，教师无法审核关系质量，没有结构性问题检测，所有角色看到的内容相同（无发布过滤）。Claude×GPT 辩论收敛的 5 阶段路线图中，Phase 1「可信骨架」解决数据可信度问题，是后续所有 Phase 的前提。

**核心命题：** 把知识图谱从"AI 生成的草稿"升级为"教师可信赖的结构"。Phase 1 不改可视化（Phase 2），只做数据质量和审查基础设施。

## §1 交付物与范围

### 交付物

| # | 交付物 | 作用 |
|---|--------|------|
| 1 | Graph API v2 响应增强 | 补齐 description/confidence + 新增 hard_in_out_count/external_hard_refs 计算字段 |
| 2 | 关系审查工作台 v1 | 教师按概念审核关系（确认/驳回/编辑），Phase 2 可视化的数据前提 |
| 3 | 质量巡检 API | 检测孤立点/弱连通分量/低置信度/跨模块硬前置异常，给审查提供优先级 |
| 4 | 发布规则 v1 | 角色感知的可见性过滤，未审核内容对学生/家长/Agent 不可见 |

### 不做的事

- 不替换力导向图为分层概念图（Phase 2）
- 不做学习进阶 schema（Phase 3）
- 不做误概念/跨学科框架（Phase 4）
- 不做 Agent 路径消费（Phase 5）

### 现有基础利用

- ConceptGraphNode 已有 description、difficulty、bloom_level、review_status、aliases_json、evidence_ids_json
- ConceptGraphEdge 已有 confidence、strength
- Edit API 已支持 set_review_status（node 三态机 ai_draft→teacher_reviewed→published）
- knowledge.db↔PG 同步机制已运行

## §2 Graph API v2 响应增强

### Node 新增字段

| 字段 | 类型 | 来源 | 说明 |
|------|------|------|------|
| `description` | string | 已有列，graph 响应未包含 | 概念一句话描述 |
| `hard_in_count` | int | 实时计算 | 指向本节点的 prerequisite_hard 边数 |
| `hard_out_count` | int | 实时计算 | 本节点指出的 prerequisite_hard 边数 |
| `external_hard_refs` | `{in: [{id, name, module}], out: [{id, name, module}]}` | 实时计算 | 跨模块硬前置关系的对端概念（仅 module 过滤时有值） |

### Edge 新增字段

| 字段 | 类型 | 来源 | 说明 |
|------|------|------|------|
| `confidence` | float | 已有列，响应未包含 | AI 生成置信度（0-1） |
| `review_status` | string | 新增列 | 关系级审核状态 |

### 计算字段实现

service 层一次 SQL 聚合查出所有 hard 边的 in/out 计数，O(1) 额外查询。external_hard_refs 只在 module 过滤时计算（筛选出跨模块边，返回对端节点摘要信息）。

## §3 Edge Review Status

### 数据库变更

`concept_graph_edges` 表新增一列：

```sql
ALTER TABLE concept_graph_edges ADD COLUMN review_status VARCHAR(20) DEFAULT 'ai_draft';
```

现有 335 条 edge 全部默认为 ai_draft。唯一的 migration 变更。

### 状态机

```
ai_draft → teacher_reviewed → published
ai_draft → rejected
rejected → ai_draft（教师撤回驳回）
teacher_reviewed → rejected（教师反悔）
```

rejected 的 edge 不删除（保留审计痕迹），但不参与发布过滤和图谱展示。

### Edit API 扩展

现有 `set_review_status` 操作扩展为支持 edge：

```json
{"op": "set_review_status", "edge_id": 42, "status": "teacher_reviewed"}
```

通过有 `edge_id` 还是 `node_id` 区分目标。批量操作直接发多条 set_review_status 即可。

### sync_service 适配

knowledge.db → PG 同步时，如果 knowledge.db edges 表有 review_status 列则读取，无则默认 ai_draft（与现有 schema-adaptive 模式一致）。backwrite 时同步 edge review_status 回 knowledge.db。

## §4 关系审查工作台 v1

### 定位

新增前端组件，嵌入 KnowledgeTreePage 右侧区域，与 GraphPanel 平级 tab 切换。教师逐概念审核关系。

### 布局

```
KnowledgeTreePage
├── 左侧: TreeNavPanel（不变）
├── 右侧模式切换: [图谱视图] / [审查工作台]  ← 新增 tab
│   ├── 图谱视图: GraphPanel（现有，不改）
│   └── 审查工作台: RelationReviewPanel（新增）
└── 抽屉: NodeDetailDrawer（不变）
```

### RelationReviewPanel 结构

```
┌──────────────┬─────────────────────────────────┐
│  概念列表     │  选中概念的关系详情               │
│  (筛选+排序)  │                                  │
│              │  ┌─ 概念卡片（名称/描述/状态）──┐  │
│ ● 细胞膜  ⚠  │  │ 细胞膜  teacher_reviewed     │  │
│ ○ 核糖体  ●  │  └────────────────────────────┘  │
│ ○ 线粒体  ○  │                                  │
│ ...         │  前置依赖 (hard) ──────────────── │
│              │  ✅ ← 细胞学说  [确认][驳回][编辑]│
│  筛选:       │  ⚠  ← 蛋白质    [确认][驳回][编辑]│
│  [模块 ▼]    │                                  │
│  [状态 ▼]    │  后继概念 (hard) ──────────────── │
│  [质量 ▼]    │  ○  → 主动运输  [确认][驳回][编辑]│
│              │                                  │
│  排序:       │  桥接/对比 ────────────────────── │
│  [优先级 ▼]  │  ○  ⇔ 通道蛋白(contrast)        │
│              │                                  │
└──────────────┴─────────────────────────────────┘
```

### 概念列表功能

- 按模块/BigConcept 分组（与左侧树一致）
- 筛选：模块、审核状态（ai_draft/teacher_reviewed/published）、质量问题标记
- 排序：默认按优先级（有质量问题的排前面）、按 display_order、按名称
- 状态徽标：● published / ⚠ 有未审核关系 / ○ ai_draft

### 关系详情功能

- 按关系类型分组：prerequisite_hard → prerequisite_soft → bridge_to → contrast
- 每条关系显示：对端概念名、置信度（低于 0.7 高亮）、审核状态
- 操作：
  - **确认**：edge review_status → teacher_reviewed
  - **驳回**：edge review_status → rejected
  - **编辑**：修改 relation_type / strength（弹窗，复用 edit API）
  - **批量确认**：选中多条同时确认

### 审查进度统计

顶部进度条：已审核关系数 / 总关系数，按关系类型分别统计。

## §5 质量巡检 API

### 端点

```
GET /api/v1/knowledge-tree/quality-check?module=M1
Permission: EDIT_KNOWLEDGE_TREE
```

### 检测规则

| ID | 规则 | 严重度 | 检测逻辑 |
|----|------|--------|----------|
| Q1 | 孤立概念 | HIGH | hard_in_count=0 且 hard_out_count=0 的 L1 节点 |
| Q2 | 弱连通分量 | MED | prerequisite_hard 子图连通分量 >1 个 |
| Q3 | 低置信度关系 | MED | confidence < 0.7 且 review_status=ai_draft 的边 |
| Q4 | 跨模块硬前置异常 | LOW | prerequisite_hard 跨 module，供人工确认 |
| Q5 | 无描述概念 | MED | description 为空或 NULL 的 L1 节点 |
| Q6 | 被驳回关系堆积 | LOW | rejected 边数超过同模块总边数 20% |

### 响应结构

```json
{
  "module": "M1",
  "summary": {
    "total_nodes": 22,
    "total_edges": 67,
    "issues_by_severity": {"HIGH": 1, "MED": 5, "LOW": 2}
  },
  "issues": [
    {
      "rule_id": "Q1",
      "severity": "HIGH",
      "message": "孤立概念：细胞骨架（无任何硬前置关系）",
      "node_ids": ["BIO_SR_CP_M1_CYTOSKELETON"],
      "edge_ids": []
    }
  ]
}
```

### 实现

纯 SQL 聚合 + Python BFS 连通分量（108 节点规模，内存计算，不引入 networkx）。新增 `quality_service.py`，纯函数式。

### 与审查工作台集成

工作台加载时自动调用一次 quality-check，将问题标记注入概念列表排序权重。

## §6 发布规则 v1

### 角色可见性矩阵

| review_status | 教师+管理员 | 学生/家长 | Agent 工具 |
|---------------|------------|----------|-----------|
| ai_draft | ✅ 可见（灰色标记） | ❌ 隐藏 | ❌ 不返回 |
| teacher_reviewed | ✅ 可见 | ✅ 可见 | ✅ 可用 |
| published | ✅ 可见 | ✅ 可见 | ✅ 可用 |
| rejected（edge） | ✅ 可见（删除线） | ❌ 隐藏 | ❌ 不返回 |

### 实现

Graph API 新增查询参数 `include_draft=true|false`：

- 教师/管理员角色：默认 `include_draft=true`
- 学生/家长角色：强制 `include_draft=false`（忽略传参）
- Agent 工具：强制 `include_draft=false`

`include_draft=false` 时：
- node 过滤：排除 review_status=ai_draft
- edge 过滤：排除 review_status 为 ai_draft 或 rejected
- edge 级联过滤：排除两端任一节点被过滤的边
- navigation 中的 concept_ids 同步过滤

### Mastery API 联动

`GET /api/v1/knowledge-tree/mastery` 遵循同样过滤——学生只看到已审核概念的掌握度。

### 宽限期配置

现有 108 个概念全部 ai_draft。为避免学生页面突然空白：

```python
# config.py
KNOWLEDGE_DRAFT_VISIBLE: bool = True  # 宽限期开关，True=draft 对所有人可见
```

教师审核达到一定比例后管理员关闭。运行时配置项，不需要重启。

## §7 变更范围总结

### 后端

| 变更 | 文件 | 说明 |
|------|------|------|
| Migration | `alembic/versions/xxx_add_edge_review_status.py` | edge 加 review_status 列 |
| Service 增强 | `modules/knowledge_tree/service.py` | graph 响应补字段 + 发布过滤 + edit 扩展 |
| 新增 service | `modules/knowledge_tree/quality_service.py` | 6 条质量巡检规则 |
| Router 增强 | `modules/knowledge_tree/router.py` | 新增 quality-check 端点 + include_draft 参数 |
| Schema 增强 | `modules/knowledge_tree/schemas.py` | 响应模型补字段 |
| Sync 适配 | `modules/knowledge_tree/sync_service.py` | edge review_status 同步 |
| 配置 | `config.py` | KNOWLEDGE_DRAFT_VISIBLE 宽限期开关 |

### 前端

| 变更 | 文件 | 说明 |
|------|------|------|
| 新增 | `components/knowledge-tree/RelationReviewPanel.vue` | 审查工作台主面板 |
| 新增 | `components/knowledge-tree/ConceptReviewList.vue` | 概念列表（筛选+排序） |
| 新增 | `components/knowledge-tree/RelationDetailCard.vue` | 单概念关系详情 |
| 新增 | `components/knowledge-tree/QualityBadge.vue` | 质量问题徽标 |
| 修改 | `pages/KnowledgeTreePage.vue` | 加 tab 切换（图谱/审查） |
| 修改 | `api/knowledgeTree.js` | 补充 qualityCheck() + include_draft 参数 |
| 修改 | `components/knowledge-tree/useKnowledgeTree.js` | 消费新字段 |

### 不改动

- GraphPanel.vue（Phase 2 替换）
- NodeDetailDrawer.vue
- TreeNavPanel.vue
- knowledge.db 表结构（仅 PG 加列 + backwrite 适配）

## §8 演进路线图（全景）

| Phase | 名称 | 核心交付 | 依赖 |
|-------|------|---------|------|
| **1** | **可信骨架（本设计）** | **Graph API v2 + 审查工作台 + 巡检 + 发布规则** | **无** |
| 2 | 教师工作台 | ConceptMapPanel（分层固定布局）+ 替换 GraphPanel | Phase 1 |
| 3 | 学习进阶 | sub_concept_progressions schema + 编辑器 + Mastery API v2 | Phase 1 |
| 4 | 教学语义 | 误概念层 + 跨学科框架 + 证据联动 | Phase 2 |
| 5 | Agent 路径 | StudyUnit 落地 + 路径生成 + 工作台 V2 三模式 | Phase 1-4 |
