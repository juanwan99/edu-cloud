# 知识图谱层级重构设计

> [2026-04-09 16:25:20 实现完成] Commits: 51f1e9d..a9aa033
> 创建：2026-04-09 11:07:14
> GPT 审查：2026-04-09 3 轮辩论收敛
> 项目：edu-cloud + edu-knowledge-base

## §0 背景与动机

### 问题

当前 knowledge.db 的图谱 API 将三层数据（L0/L1/L2）共 1233 个节点拍平返回。其中 89%（1103 个）是 L0 原子事实——教材逐句提取的长句子，无关系、无层级、`module: "unknown"`。真正有结构的 108 个 L1 概念被淹没在噪声中。

### 调查发现

L1 层数据质量其实不错：94% 命名 ≤10 字符（"细胞学说"、"糖类"），有别名、课标锚点、335 条前置依赖关系。但 `parent/children` 层级形同虚设（children 全空），`aliases` 只在 JSON 骨架中未入库。

### 目标

建立既对人类友好（教师能浏览、搜索、审核、编辑）又对机器友好（Agent 做 BKT 诊断、自适应推荐、学习路径规划）的知识图谱。

### 约束

| 约束 | 决定 |
|------|------|
| 首要用户 | 教师 > Agent > 家长/学生 |
| 维护模式 | AI 生成 + 人工审核，未来引入教研组 |
| 多学科 | 架构支持，实现先做生物 |
| 层级结构 | 混合（课标锚点 + 教材对齐 + L0 降级为详情） |
| BKT 粒度 | DA 级（已有架构，不变） |

## §1 数据层级模型

### 四层导航 + 独立维度

```
导航层（课程组织视角）           图谱层（知识关系视角）        诊断层（自适应视角）
─────────────────           ─────────────────        ─────────────────
Subject（学科）
  └─ Module（课标一级主题）
       └─ BigConcept（课标大概念）
            └─ Concept（L1 知识点）  ←── 图谱主节点 + edges ──→  DA → BKT
                 └─ Evidence（L0）        335 条关系               掌握度追踪
```

**三个维度独立，不互为父层**（Claude×GPT 共识）：

| 维度 | 职责 | 回答的问题 |
|------|------|-----------|
| BigConcept（导航层） | 课程导航容器 | "这个概念在课程框架里归哪组" |
| StudyUnit（规划层） | 学习规划单元 | "这个学生下一步学什么" |
| sub_concept_progressions（进阶层） | 掌握水平分级 | "这个概念学到哪一层了" |

三者最多通过 Concept 做派生关联，不存储直接关系。

**关键规则：**

- 图谱可视化只画 Concept 层 + 它们之间的 edges（335 条）
- Module 和 BigConcept 是**导航容器**，不是图上的节点
- Evidence（原 L0）是详情面板内容，永远不出现在图上
- L2（22 条跨模块原理）作为 BigConcept 之间的跨模块标注

**Concept 节点必备属性：**

| 属性 | 类型 | 来源 | 说明 |
|------|------|------|------|
| id | TEXT | 现有 | `BIO_SR_CP_M1_CELL_THEORY` |
| canonical_name | TEXT | 现有 | 简洁术语，教师看到的 |
| aliases_json | TEXT | JSON 迁移 | `["质膜","细胞质膜"]`，支持搜索 |
| module | TEXT | 现有 | M1-M5 |
| display_order | INT | 新增 | 同一 BigConcept 下的排列顺序 |
| review_status | TEXT | 新增 | `ai_draft` / `teacher_reviewed` / `published` |
| reviewed_by | TEXT | 新增 | 审核人 |
| reviewed_at | TEXT | 新增 | 审核时间 |
| difficulty | INT | 新增 | 1-5，教师辅助标签（未来可接入选题器） |
| difficulty_source | TEXT | 新增 | `ai_inferred` / `teacher_set` / `imported` |
| bloom_level | TEXT | 新增 | 记忆/理解/应用/分析/评价/创造 |
| bloom_source | TEXT | 新增 | `ai_inferred` / `teacher_set` / `imported` |
| description | TEXT | 现有 | 一句话描述 |
| chapter_refs | TEXT | 现有 | 教材章节定位 |
| req_ids | TEXT | 现有 | 课标条款锚点 |

> **注意**：`difficulty`/`bloom_level` 定位为教师辅助标签。当前自适应选题器只按 `transfer_band` 选题，这两个字段暂无代码消费方。

## §2 Schema 变更（knowledge.db）

原则：只加不删，现有表结构不破坏。

### 新增表：big_concepts

```sql
CREATE TABLE IF NOT EXISTS big_concepts (
    id TEXT PRIMARY KEY,              -- 稳定 ID，如 'BC_BIO_M1_CELL_STRUCTURE'
    subject TEXT NOT NULL,            -- 'biology_senior'
    module TEXT NOT NULL,             -- M1-M5
    name TEXT NOT NULL,               -- '细胞的基本结构'
    description TEXT,
    source_req_ids TEXT,              -- 对应课标条款 JSON array
    display_order INTEGER NOT NULL DEFAULT 0,
    review_status TEXT NOT NULL DEFAULT 'published'
);
```

数据来源：从 `curriculum_requirements.big_concept` 字段聚合，预计 ~25 个。一次性脚本生成初稿，人工校对。

> **ID 规范**：`BC_{SUBJECT}_{MODULE}_{SLUG}`。不用 big_concept 文本当主键。

### 新增表：concept_big_concept_map（多对多映射）

```sql
CREATE TABLE concept_big_concept_map (
    concept_id TEXT NOT NULL REFERENCES concepts(id),
    big_concept_id TEXT NOT NULL REFERENCES big_concepts(id),
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    confidence REAL NOT NULL DEFAULT 1.0,
    source TEXT NOT NULL DEFAULT 'ai_inferred',   -- ai_inferred / teacher_confirmed / imported
    reviewed_by TEXT,
    reviewed_at TEXT,
    PRIMARY KEY (concept_id, big_concept_id),
    CHECK (confidence >= 0 AND confidence <= 1)
);

-- 每个 concept 至多一个 primary BigConcept（数据库级约束）
CREATE UNIQUE INDEX ux_cbc_primary
ON concept_big_concept_map(concept_id)
WHERE is_primary = TRUE;
```

**设计决策**（Claude×GPT 辩论共识）：

- 用映射表而非 `concepts.parent_id` 单 FK。原因：实测有 2 个 L1 概念跨多个 BigConcept，教育领域常态。
- `is_primary` 默认 FALSE，部分唯一索引强制约束。多归属概念需人工指定 primary。
- 审核字段放在映射行上，因为审核对象是"归属关系"。
- 发布规则：`published` 状态的 concept 必须恰好有一个 `is_primary=TRUE` 的映射。

### concepts 表加列

```sql
ALTER TABLE concepts ADD COLUMN aliases_json TEXT;
ALTER TABLE concepts ADD COLUMN evidence_ids_json TEXT;    -- 原 l0_ids，从 JSON 骨架迁移
ALTER TABLE concepts ADD COLUMN display_order INTEGER DEFAULT 0;
ALTER TABLE concepts ADD COLUMN review_status TEXT DEFAULT 'ai_draft';
ALTER TABLE concepts ADD COLUMN reviewed_by TEXT;
ALTER TABLE concepts ADD COLUMN reviewed_at TEXT;
ALTER TABLE concepts ADD COLUMN difficulty INTEGER;
ALTER TABLE concepts ADD COLUMN difficulty_source TEXT DEFAULT 'ai_inferred';
ALTER TABLE concepts ADD COLUMN bloom_level TEXT;
ALTER TABLE concepts ADD COLUMN bloom_source TEXT DEFAULT 'ai_inferred';
```

**审核状态机**：`ai_draft` → `teacher_reviewed` → `published`。已发布概念被修改时自动回退到 `ai_draft`。

### L0 重分类

```sql
UPDATE concepts SET knowledge_level = 'evidence' WHERE knowledge_level = 'L0';
```

不删数据，只改标签。Graph API 用 `WHERE knowledge_level IN ('L1','L2')` 过滤。

### concept_relations 表不变

已有 schema 满足需求（source_id, target_id, relation_type, confidence, strength）。335 条 L1-L1 关系保持不变。

### PG 同步适配

concept_graph_nodes 表加列：

```sql
subject TEXT                       -- 多学科隔离（必须）
node_type TEXT DEFAULT 'concept'   -- 'concept' | 'big_concept'
display_order INTEGER
review_status TEXT
aliases_json TEXT
```

sync_service.py 改为：
- 只同步 `knowledge_level = 'L1'` 的 concepts
- 新增同步 `big_concepts` 表和 `concept_big_concept_map` 表
- 携带新字段（review_status, aliases_json, subject 等）

> **数据源分离**（Claude×GPT 共识）：迁移脚本从 JSON 骨架生成 map → 写入 knowledge.db 新表 → sync_service 从 knowledge.db 新表读取。sync_service 不直接读 JSON 文件。

## §3 API 层变更

### Graph API 改造

`GET /api/v1/knowledge-tree/graph` 响应格式：

```json
{
  "navigation": [
    {
      "id": "M1", "name": "分子与细胞",
      "big_concepts": [
        {
          "id": "BC_BIO_M1_CELL_STRUCTURE",
          "name": "细胞的基本结构",
          "concept_ids": ["BIO_SR_CP_M1_MEMBRANE", "BIO_SR_CP_M1_ORGANELLE"]
        }
      ]
    }
  ],
  "graph": {
    "nodes": [
      {
        "id": "BIO_SR_CP_M1_MEMBRANE",
        "name": "细胞膜的结构和功能",
        "aliases": ["质膜", "细胞质膜"],
        "module": "M1",
        "big_concept_id": "BC_BIO_M1_CELL_STRUCTURE",
        "review_status": "ai_draft",
        "difficulty": 3,
        "bloom_level": "understand"
      }
    ],
    "edges": [
      {"source": "...", "target": "...", "type": "prerequisite_hard", "strength": 0.9}
    ]
  }
}
```

**关键变化**（Claude×GPT 共识）：
- `navigation` 是显式一等契约字段，从 big_concepts + map 动态构建，不从平铺节点拼装
- `graph.nodes` 只包含 L1 概念（108 个），`big_concept_id` 取 `is_primary=TRUE` 的归属
- `module` 过滤参数保留（`?module=M1`）
- 导航基础事实持久化（big_concepts + map + display_order），导航树状 JSON 动态构建

### Node Detail API 扩展

追加 evidence 段（L0 条目列表）：

```json
{
  "concept": { ... },
  "evidence": [
    {"id": "BIO_SR_B1_CH03_BK_001", "text": "细胞作为基本的生命系统…"}
  ],
  "das": [...],
  "curriculum": [...],
  "textbook": [...],
  "questions": {...}
}
```

### 新增：搜索 API

```
GET /api/v1/knowledge-tree/search?q=质膜
```

在 canonical_name、aliases_json、description 上做模糊匹配，返回匹配的 L1 概念列表。

### 编辑 API 扩展

新增操作类型：

| 操作 | 说明 | 权限 |
|------|------|------|
| update_concept | 改名称/别名/描述/难度/布鲁姆 | EDIT_KNOWLEDGE_TREE |
| set_review_status | 标记审核状态 | EDIT_KNOWLEDGE_TREE |
| reorder | 调整同组内排序 | EDIT_KNOWLEDGE_TREE |

教师不能增删 BigConcept 和 Module（课标锚点，管理员/迁移脚本管理）。

## §4 前端变更

### TreeNavPanel：三级树形导航

```
▼ M1 分子与细胞
    ▼ 细胞学说与科学史
        ● 细胞学说          ○ 已审
        ● 细胞发现科学史    ◐ 草稿
    ▶ 细胞的分子组成
    ▶ 细胞的基本结构
▶ M2 遗传与进化
```

- 从 API 的 `navigation` 字段直接渲染，**一次性切断旧的平铺拼装逻辑**
- 点击 L1 概念：右侧图谱高亮 + 打开详情抽屉
- 搜索框：实时过滤树 + 高亮匹配节点
- 审核状态图标：`●` 已发布 / `◐` 已审核 / `○` AI 草稿

### GraphPanel：模块级力导向图

- 默认视图：当前模块的 L1 概念 + edges（~35 节点/模块）
- 节点大小 = DA 数量，颜色 = 掌握度或审核状态
- 全局视图：5 个模块聚类，模块间用 L2 关系连线

### NodeDetailDrawer：扩展详情 + 编辑

新增：evidence 段、难度/布鲁姆选择、审核状态按钮、别名编辑。
不可编辑：L0 证据、课标要求、DA（数据管线管理）。

## §5 数据迁移

### 迁移脚本 `scripts/migrate_knowledge_hierarchy.py`

**数据源**：直接读 `skeleton/L1/*.json`（不依赖 knowledge.db 的 source_req_id 单值字段，避免丢失多归属）。

**Step 1** — 从 `curriculum_requirements.big_concept` 聚合生成 BigConcept（~25 个），输出 CSV 供人工校对，确认后写入 `big_concepts` 表。

**Step 2** — 从 L1 JSON 骨架读取 `req_ids`（多值），通过 `req_ids → curriculum_requirements.big_concept` 构建 `concept_big_concept_map`：
- 106 个单归属：自动设 `is_primary=TRUE`，`source='ai_inferred'`
- 2 个多归属：所有映射 `is_primary=FALSE`，标记待人工指定 primary
- 写入 knowledge.db

**Step 3** — 从 L1 JSON 骨架迁移 aliases → `aliases_json`，l0_ids → `evidence_ids_json`。

**Step 4** — `UPDATE concepts SET knowledge_level = 'evidence' WHERE knowledge_level = 'L0'`

**Step 5** — 初始化默认值：`difficulty=3, difficulty_source='ai_inferred', bloom_level='understand', bloom_source='ai_inferred', review_status='ai_draft'`

**幂等性**：所有 INSERT 使用 `INSERT OR IGNORE`，UPDATE 使用条件更新。脚本可重复执行。

### 迁移验证清单

| 检查项 | 预期 |
|--------|------|
| big_concepts 行数 | 20-30 |
| concept_big_concept_map 行数 | 108-110（106 单归属 + 2×2 多归属） |
| is_primary=TRUE 的行数 | 106（2 个多归属待人工指定） |
| L1 有 aliases_json 比例 | 100% |
| evidence（原 L0）行数 | 1103 |
| concept_relations 行数 | 335（不变） |

### 可回滚性

所有变更为 ADD COLUMN / CREATE TABLE / INSERT / UPDATE，不删数据。

## §6 多学科扩展策略

### 单库方案

所有学科在同一个 knowledge.db，通过 `subject` 字段隔离。PG 投影表（concept_graph_nodes）必须有 `subject` 列 + API 过滤。

### ID 体系

```
概念:    {SUBJECT}_{LEVEL}_{MODULE}_{SLUG}     BIO_SR_CP_M1_CELL_THEORY
大概念:  BC_{SUBJECT}_{MODULE}_{SLUG}          BC_BIO_M1_CELL_STRUCTURE
模块:    {SUBJECT}_{MODULE}                    BIO_M1
```

现有生物 ID 已符合规范，不需迁移。

### 本期不做

- 跨学科关系、学科切换 UI、学科级权限隔离

## §7 集成点

### 零改动

| 系统 | 原因 |
|------|------|
| BKT 引擎（student_da_mastery） | DA 级追踪，L1 ID 不变，映射不动 |
| adaptive 选题器 | 消费 DA + q_matrix |
| answer_logs → BKT 管道 | 不涉及图谱层级 |
| Agent 工具 diagnose_and_recommend | 读 DA mastery |
| Agent 工具 edit_knowledge_graph | 操作 L1 节点 |

> **BKT 兼容性**：本次设计不改任何 L1 ID，DA→concept 映射不变，不影响历史掌握度。未来若需拆并概念，需引入映射版本化（V2 范围）。

### 需适配

| 模块 | 变更量 | 说明 |
|------|--------|------|
| sync_service.py | ~60 行 | 同步 L1 + big_concepts + map，携带新字段 |
| Graph API (service.py + router.py) | ~120 行 | navigation 构建 + 分层查询 + 新响应格式 |
| detail_service.py | ~20 行 | 追加 evidence 段 + 多归属展示 |
| TreeNavPanel.vue | ~200 行重写 | 模块卡片 → 三级树 |
| GraphPanel.vue | ~50 行 | 节点数降到 ~35/模块，参数调优 |
| NodeDetailDrawer.vue | ~100 行 | evidence + 编辑字段 + 审核按钮 |
| Search API（新增） | ~30 行 | name + aliases 模糊匹配 |
| Alembic migration | ~30 行 | concept_graph_nodes 加列 + subject |

### 工作量估计

| 模块 | 天数 |
|------|------|
| 迁移脚本 + BigConcept 生成 + 人工校对 | 1 |
| Schema 变更（knowledge.db + PG Alembic） | 0.5 |
| sync_service 适配 | 1 |
| Graph API + Search API + Detail API | 1 |
| 前端三组件改造 | 2 |
| 测试 | 1 |
| **合计** | **~6.5 天** |

## §待处置（Plan Review R3 design-concern）

1. **R3-F001 (accepted-risk): BigConcept 存储在 concept_graph_nodes 表** — GPT 建议独立投影表。决定：accepted-risk。理由：type discrimination（node_type 字段）是标准做法，所有消费路径（graph/mastery/search/edit）已有过滤，106+11 条记录拆表收益不抵 JOIN 复杂度增量。如果未来 BigConcept 需要独立属性（如 description、ordering_rules）超出 concept_graph_nodes 列集，再考虑拆表。
2. **R3-F006 (deferred, deadline 2026-04-30): Contract Pack YAML 格式化** — GPT 要求按 contract-pack-schema.md 使用 YAML 根键格式。当前 Markdown 格式功能等价，延期到全局 Contract Pack 工具链统一时处理。

## §8 GPT 独立评审附录

### GPT 最终评价

> 修订后设计已经从"可能把课程导航硬塞进图谱主结构"的高风险方案，收敛成了职责清晰、教育语义正确、工程上可落地的方案。BigConcept 只做课程导航容器，Concept 继续作为图谱主节点，DA/BKT 主链不被破坏，L0 留在 evidence 层，StudyUnit 与学习进阶维持独立维度。这套设计可以进入实施，不再有架构级硬伤。

### Top 3 实施风险

1. **迁移一致性**：JSON → knowledge.db 新表的写回必须幂等，否则后续同步漂移
2. **约束落地**：is_primary 唯一索引、published 状态机、审核回退——漏一条数据就脏
3. **前后端契约切换**：一次性切断旧的平铺拼装逻辑，不要新旧混用导致双轨 bug

### 关键修订记录（辩论驱动）

| # | 原设计 | 修订为 | 驱动 |
|---|--------|--------|------|
| 1 | concepts.parent_id 单 FK | concept_big_concept_map 多对多 | GPT: 2 个 L1 跨多 BigConcept |
| 2 | is_primary 默认 TRUE | 默认 FALSE + 部分唯一索引 | GPT: 防脏数据 |
| 3 | sync 读 knowledge.db source_req_id | 迁移读 JSON 骨架→写 DB→sync 读 DB | GPT: source_req_id 单值丢多归属 |
| 4 | API modules 嵌套字段 | 显式 navigation 一等契约字段 | GPT: 导航不能隐式存在 |
| 5 | review_status 单枚举 | + reviewed_by/reviewed_at + published 回退 | GPT: 最低审核可追溯 |
| 6 | difficulty/bloom_level 无来源 | + source 字段 + 定位为教师标签 | GPT: 防脏数据 + 不冒充 adaptive |
| 7 | 维度关系未定义 | BigConcept/StudyUnit/Progressions 独立 | GPT: 课程导航≠学习规划≠进阶 |
