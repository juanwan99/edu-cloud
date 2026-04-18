# 知识图谱深度优化设计

> **项目**: edu-cloud 知识图谱模块
> **目标**: 让教师看到清晰的知识图谱 → 规划教学 → 学生画像 → 智能推送
> **创建**: 2026-04-12 23:11:57
> **状态**: Phase 1 [实现完成]

> [2026-04-18 15:25:00 Phase 1 实现完成] Commits 链: Batch 1 `1c3c1a2..bcb1971` (T1-T6) / Batch 2 `d300263` (T7-T8) / Batch 3.a `2ab10a2..c5bff80` (T9-T10) / Batch 3.b `66ab2b8..317dfb6` (T11-T12) + Batch 3.b.iii `121a6c9..ad7e957` + Batch 3.b.iv `43264e1..2b97201` (fetchSeq guard 3 路径 mutant 锁) / Batch 3.c `865032f..<T14 sha>` (T13-T14 收尾)。Phase 1 14 Task 全部完成。test_debt 保留：TD-005 (F001 Task 11 shows empty state 弱断言) / TD-006 (P0-F001 Contract Pack INV-004/CE-002 映射漂移) / 后端 P001 `test_exam_frequency_l1_set_equals_kb_l1` — 均 deferred 到 Phase 2。
>
> Phase 2/3/4 待后续规划（Phase 2: L2 大概念层 + 学习路径；Phase 3: 跨模块桥接/对比边 + 焦点模式 Phase 2 高级； Phase 4: 学生画像深度）。

---

## §0 调查结论：数据 80% 已就绪，0% 已暴露

### 0.1 关键纠正

此前判断"高考真题与图谱断裂"是错误的。实际存在完整的 3-hop 关联链路：

```
assessment_items (2,448 题, 95.6% 有标注)
    ↓ task_model_id
task_models (134 个)
    ↓ target_attribute_ids
diagnostic_attributes (156 个, 100% 有 linked_concept_ids)
    ↓ linked_concept_ids
concepts (L1: 108 个)
```

Q-Matrix 14,872 条记录桥接了题目和 DA。通过这条链路可以**直接计算**每个 L1 概念的高考考频。实测结果：

| 概念 | 考频（题） | 概念 | 考频（题） |
|------|-----------|------|-----------|
| ATP与细胞能量货币 | 1313 | 酶 | 653 |
| 细胞呼吸 | 1295 | 细胞周期与有丝分裂 | 642 |
| 光合作用 | 1260 | 核酸 | 629 |
| 糖类 | 748 | 分泌蛋白的合成与运输 | 618 |
| 细胞器的结构与功能 | 738 | 细胞膜的结构与功能 | 555 |

考频范围：0-1313，中位数 11，零考频概念 19/108。

同理，教材章节映射也存在（89.5% 覆盖），只是未在图谱 API 暴露。

### 0.2 数据资产全景

| 资产 | 数量 | 完整度 | 在图谱中暴露？ |
|------|------|--------|--------------|
| L1 概念 | 108 | 100%（difficulty/bloom/aliases 全填充）| ✅ 基础节点 |
| L2 原理 | 22 | 100% | ❌ 未在图谱展示 |
| BigConcept | 10 | 100% | ✅ 导航分组 |
| Evidence (L0) | 1,103 | 89.5% 有教材锚点 | ❌ 仅在详情面板 |
| 前置依赖边 | 335 (hard:147/soft:128/bridge:31/contrast:29) | 完整 | ⚠️ 仅 hard 参与布局 |
| DA 诊断属性 | 156 | 100% 有行为描述和概念链接 | ❌ 仅在详情面板 |
| 高考真题 | 2,448 | 95.6% 有 DA 标注 | ❌ 完全未暴露 |
| Q-Matrix | 14,872 | 100% | ❌ 完全未暴露 |
| StudyUnit | 99 | 100%（前置/时间/教材全链接）| ❌ 完全未暴露 |
| 课标要求 | 175 | 100% 映射到大概念 | ❌ 仅在详情面板 |
| 教材内容块 | 2,135 | 100% | ❌ 仅模糊搜索 |
| MCU 规划权重 | 112 CP（exam_freq/error_prone/transfer_value） | 100% | ❌ 未迁入 |

### 0.3 真正的问题重新定义

| # | 问题 | 本质 | 影响 |
|---|------|------|------|
| **P1** | 图谱节点"一视同仁" | 考频/权重/难度数据存在但未暴露到图谱 API | 教师看不出重点 |
| **P2** | 教材章节不可见 | 89.5% 的教材锚点未在图谱维度呈现 | 教师无法按章节导航 |
| **P3** | 图谱边偏少 | 108 节点 147 硬边，46 个节点出度为 0 | 教学序列不可靠 |
| **P4** | soft/bridge/contrast 边被浪费 | 188 条非硬前置边不参与可视化 | 横向关联缺失 |
| **P5** | 高考真题不可见 | 2,448 题未在图谱/详情中关联展示 | 教师无法"看这个概念考了什么" |
| **P6** | 教学规划功能为零 | 无教学日历、进度追踪 | 无法服务"规划教学" |
| **P7** | 学生数据管线断 | BKT 架构完整但 answer_logs 为空 | 画像全灰 |
| **P8** | StudyUnit 未利用 | 99 个学习单元（含课时/前置/练习）完全未暴露 | 浪费最有价值的教学单元 |

---

## §1 设计目标与约束

### 1.1 四条价值链

```
链1: 教师看图谱    — 打开页面立刻看到「什么重要、什么考、怎么关联」
链2: 规划教学      — 按章节/学期安排教学顺序，系统提供建议序列
链3: 学生画像      — 每个学生在图谱上有独立的掌握度着色
链4: 智能推送      — 根据薄弱点 + 前置依赖推荐学什么、练什么题
```

### 1.2 约束

- **不改 knowledge.db schema**：knowledge.db 是上游资产，edu-cloud 只做投影消费
- **PG 可扩展**：edu-cloud 的 PostgreSQL 表可以新增列和表
- **前端增量扩展**：当前架构评估为"扩展友好"，不需要大重构
- **MCU-03 作为素材来源**：不是"吸收 MCU"，是从 MCU 提取对目标有用的数据

### 1.3 不做什么

- 不新建知识骨架体系（已有的够用）
- 不做多学科泛化（先生物做透）
- 不做实时协同编辑
- 不做 L3 思维模式可视化（过于抽象，教师不需要）

---

## §2 架构方案

### 2.1 核心思路：计算层 + 投影层

```
                knowledge.db (真源, 只读)
                     │
              ┌──────┴──────┐
              │ 同步 + 计算  │  ← 启动时执行
              └──────┬──────┘
                     │
         ┌───────────┼───────────┐
         │           │           │
    PG 节点表     PG 边表    PG 计算表 (新)
  (已有, 扩列)  (已有)    concept_stats
         │           │           │
         └───────────┼───────────┘
                     │
              Graph API v3
           (合并计算指标返回)
                     │
              前端 G6 图谱
         (考频/权重/掌握度 着色)
```

### 2.2 新增数据模型

#### concept_stats 表（PG，启动计算/定期刷新）

```sql
CREATE TABLE concept_stats (
    concept_id   VARCHAR(64) PRIMARY KEY REFERENCES concept_graph_nodes(id),
    exam_frequency    INT    NOT NULL DEFAULT 0,   -- 关联高考题数量
    exam_coverage     FLOAT  NOT NULL DEFAULT 0.0, -- 覆盖的考试卷数/总卷数
    avg_difficulty    FLOAT,                        -- 关联题目平均难度
    importance_score  FLOAT  NOT NULL DEFAULT 0.0,  -- 综合重要度 (0-10)
    planning_weight   JSON,                         -- MCU 规划权重 {exam_freq, error_prone, transfer_value, priority_score}
    textbook_chapters JSON   NOT NULL DEFAULT '[]', -- 教材章节列表 [{book, chapter, section, title}]
    study_unit_id     VARCHAR(64),                   -- 关联的 StudyUnit ID
    estimated_minutes INT,                           -- 建议学习时间（来自 SU）
    prerequisite_depth INT   NOT NULL DEFAULT 0,     -- 前置链最大深度（拓扑排序 rank）
    computed_at       TIMESTAMP NOT NULL
);
```

#### teaching_plan 表（PG，教学规划）

```sql
CREATE TABLE teaching_plans (
    id           SERIAL PRIMARY KEY,
    school_id    VARCHAR(64) NOT NULL REFERENCES schools(id),
    class_id     VARCHAR(64),          -- NULL=全校通用
    module       VARCHAR(10) NOT NULL, -- M1-M5
    semester     VARCHAR(20) NOT NULL, -- 2026-spring
    created_by   VARCHAR(64) NOT NULL REFERENCES users(id),
    status       VARCHAR(20) NOT NULL DEFAULT 'draft', -- draft/active/archived
    created_at   TIMESTAMP NOT NULL,
    updated_at   TIMESTAMP NOT NULL
);

CREATE TABLE teaching_plan_items (
    id           SERIAL PRIMARY KEY,
    plan_id      INT NOT NULL REFERENCES teaching_plans(id),
    concept_id   VARCHAR(64) NOT NULL REFERENCES concept_graph_nodes(id),
    planned_week INT,                  -- 教学周次
    planned_date DATE,                 -- 计划教学日期
    actual_date  DATE,                 -- 实际完成日期
    status       VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending/in_progress/completed/skipped
    notes        TEXT,
    display_order INT NOT NULL DEFAULT 0
);
```

### 2.3 Graph API v3 扩展

当前 `GET /api/v1/knowledge-tree/graph` 返回的 node 结构扩展：

```json
{
  "id": "BIO_SR_CP_M1_PHOTOSYNTHESIS",
  "name": "光合作用",
  "level": "L1",
  "module": "M1",
  "big_concept_id": "BC_BIO_M1_C2",
  "difficulty": 4,
  "bloom_level": "understand",
  "review_status": "ai_draft",
  "hard_in_count": 11,
  "hard_out_count": 3,
  // ---- v3 新增 ----
  "exam_frequency": 1260,
  "importance_score": 9.2,
  "estimated_minutes": 120,
  "textbook_chapters": ["b1:ch05_s04"],
  "study_unit_id": "su:bio_sr:m1_photosynthesis",
  "planning_weight": {
    "exam_freq": 10,
    "error_prone": 8,
    "transfer_value": 9,
    "priority_score": 9.1
  }
}
```

新增 API 端点：

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/knowledge-tree/graph/{node_id}/exam-items` | 概念关联的高考真题列表（分页，含题干/难度/年份） |
| GET | `/knowledge-tree/stats/overview` | 全模块统计概览（概念数/边数/考频分布/覆盖率） |
| GET | `/knowledge-tree/teaching-sequence` | 建议教学序列（拓扑排序 + 权重优先） |
| CRUD | `/knowledge-tree/teaching-plans` | 教学计划 CRUD |
| GET | `/knowledge-tree/teaching-plans/{id}/progress` | 教学进度追踪 |

---

## §3 分阶段实施方案

### Phase 1: 数据暴露 —— "让已有的数据可见"

**目标**: 教师打开图谱立刻能看到考频、重要度、教材定位。

**核心工作**:

1. **concept_stats 计算服务** — 启动时遍历 knowledge.db 关联链路，计算每个 L1 概念的考频、重要度、教材章节，写入 PG `concept_stats` 表
2. **MCU 规划权重迁入** — 读取 MCU `planning_weights_L1.json`，通过语义匹配（概念名↔CP content）建立 MCU CP ID → knowledge.db concept ID 映射表，将 `priority_score` 等字段写入 `concept_stats.planning_weight`
3. **Graph API v3** — `get_graph()` 查询时 LEFT JOIN `concept_stats`，将统计指标合并到节点数据返回
4. **前端节点视觉升级**:
   - 节点大小 ∝ `importance_score`（重要概念更大）
   - 节点颜色 = 考频热力（高频→深色，低频→浅色）
   - 新增图例（考频/重要度/掌握度 三种着色模式切换）
5. **详情面板增强** — NodeDetailDrawer 新增"高考真题"标签页，展示关联题目列表（题干、年份、难度、题型）
6. **教材章节维度** — TreeNavPanel 增加"按教材章节"导航模式（与现有"按模块"并列）

**数据流**:

```
knowledge.db                    MCU-03
    │                              │
    ├─ DA.linked_concept_ids       ├─ planning_weights_L1.json
    ├─ q_matrix (item↔DA)          │   (112 CP × {exam_freq, error_prone,
    ├─ assessment_items            │    transfer_value, priority_score})
    ├─ concepts.source_block_id    │
    ├─ content_blocks.section_id   ├─ MCU CP ID → kb concept ID 映射
    └─ study_units                 │   (通过概念名语义匹配, ~90% 自动)
         │                         │
         └─────────┬───────────────┘
                   ↓
           concept_stats (PG)
                   ↓
            Graph API v3
                   ↓
            前端 G6 节点
         (大小/颜色/图例/详情)
```

### Phase 2: 图谱增强 —— "让图结构更完整"

**目标**: 教师看到有意义的横向关联，不再是稀疏的树状图。

**核心工作**:

1. **soft 边可视化** — 前端增加图层切换：`硬前置`（默认）/ `全部关系`（含 soft/bridge/contrast）。soft 用虚线，bridge 用彩色，contrast 用双向红线
2. **高考关联概念推断** — 通过 Q-Matrix 计算"共现频率"：两个概念在同一道题中被 DA 同时关联的次数。共现 ≥5 次的概念对创建 `co_tested` 边
3. **concept_stats.prerequisite_depth** — 拓扑排序计算每个概念的前置链深度，用于教学序列建议
4. **概念关系强度可视化** — 边的粗细 ∝ strength × confidence，弱边细+透明

**数据量预估**:

| 当前 | 增强后 | 来源 |
|------|--------|------|
| 147 硬前置边 | 147 | 不变 |
| 0 可见 soft 边 | +128 | 已有，开放可视化 |
| 0 可见 bridge 边 | +31 | 已有，开放可视化 |
| 0 可见 contrast 边 | +29 | 已有，开放可视化 |
| 0 共现边 | +约 50-100 | Q-Matrix 计算 |
| **147 总边** | **~400-450 总边** | |

### Phase 3: 教学规划 —— "帮教师排课"

**目标**: 教师可以在图谱上规划"什么时候教什么"，系统给出建议序列。

**核心工作**:

1. **建议教学序列 API** — 基于拓扑排序（前置依赖）+ 教材章节顺序 + importance_score 加权，生成建议教学序列。输入：module、学期周数。输出：concept_id 有序列表 + 每周建议概念数
2. **教学计划 CRUD** — teaching_plans + teaching_plan_items 表，支持创建/编辑/归档
3. **教学进度可视化** — 图谱上已教概念标记（如绿色勾），计划中概念标记（如蓝色边框），未计划概念灰色。支持按周查看
4. **StudyUnit 暴露** — 每个概念的学习单元信息（建议课时、前置学习单元、教材定位、练习家族）在详情面板展示

**教学序列算法**:

```
输入: module, total_weeks, teaching_hours_per_week
输出: [{week: 1, concepts: [c1, c2], estimated_hours: 3.5}, ...]

1. 拓扑排序所有 L1 概念 (prerequisite_hard DAG)
2. 按 importance_score 降序排列同 rank 概念
3. 按教材章节顺序调整（同 rank 同 importance 时，教材章节靠前的优先）
4. 装箱算法：按 estimated_minutes 将概念分配到各周（约束：不超过 teaching_hours_per_week，不打破前置依赖）
5. 输出周计划 + 依据说明
```

### Phase 4: 学生画像与推荐 —— "个性化着色和推题"

**目标**: 每个学生在图谱上看到自己的掌握度，系统推荐下一步学什么。

**核心工作**:

1. **答题数据管线** — exam-ai 考试完成后，答题结果通过 sync API 写入 `answer_logs`，触发 BKT 更新 `student_da_mastery`
2. **掌握度图谱着色** — 教师选择学生后，图谱节点按 4 态着色（solid→绿/fragile→黄/weak→红/unseen→灰）。API 已支持（`get_mastery`），前端着色逻辑已有基础（`nodesWithMastery` computed），需要完成 ConceptMapPanel 的节点颜色集成
3. **学习推荐 API** — 输入：student_id。输出：推荐学习的概念列表（按优先级排序），每个概念附带原因（"前置已掌握但此概念薄弱"/"高考高频但未掌握"等）。推荐公式：`score = importance_score × (1 - mastery) × prerequisite_readiness`
4. **推荐练习题** — 通过 Q-Matrix 反向查找：学生薄弱 DA → 关联 assessment_items（按 transfer_band 排序：near→mid→far 渐进）

**数据管线**:

```
exam-ai 考试完成
    ↓ POST /api/v1/sync/exam-results
edu-cloud 接收答题数据
    ↓ 写入 answer_logs
BKT 引擎更新
    ↓ 更新 student_da_mastery
    ↓ 聚合到 concept 级别
前端请求 GET /mastery?student_id=xxx
    ↓
图谱节点着色
```

---

## §4 MCU-03 数据迁入方案

### 4.1 迁入什么（仅服务于四个目标）

| MCU 资产 | 迁入目标 | 方式 | 价值 |
|---------|---------|------|------|
| **planning_weights_L1** (112 CP) | concept_stats.planning_weight | 语义匹配 MCU CP → kb concept | 教学规划权重 |
| **L1 horizontal_relations** | 验证现有 concept_relations | 交叉检查 co_learn/contrasts | 边补全参考 |

### 4.2 不迁入什么（及理由）

| MCU 资产 | 不迁入理由 |
|---------|-----------|
| L0 BK 1012 条 | knowledge.db 已有 1103 evidence，从教材独立提取，质量更高 |
| L1 CP 218 条 | knowledge.db 的 108 L1 以课标大概念为锚点，粒度适合教师 |
| L2 PR 81 条 | 教师不需要看抽象原理，图谱保持 L1 粒度 |
| L3 TP 12 条 | 思维模式对可视化无直接价值 |
| Topics 30 条 | 教材章节已有 119 sections 覆盖，不需要 MCU 的 topics |
| Procedures 50 条 | 操作程序面向学生学习，不服务于教师图谱 |
| IA 39 条 | 隐性假设面向诊断引擎，不服务于教师图谱 |
| 题目标注 2826 题 | knowledge.db 已有 2448 题 + Q-Matrix 14872，体系独立 |
| 诊断规则 | knowledge.db 有 DA 体系 + Q-Matrix，不需要 MCU 诊断码 |

### 4.3 MCU CP→概念映射方案

MCU 用讲次编号（`L01_CP_001`），knowledge.db 用语义 ID（`BIO_SR_CP_M1_CELL_THEORY`）。

**映射策略**:
1. 读取 MCU `L1_patterns/*.json`，提取每个 CP 的 `content`（如"生命系统的层级中，细胞是最基本..."）
2. 读取 knowledge.db L1 concepts 的 `name` + `description`
3. 基于文本相似度（TF-IDF 或 embedding）计算 MCU CP ↔ kb concept 相似度
4. 相似度 > 0.7 自动映射，0.4-0.7 人工确认，< 0.4 放弃
5. 预估结果：~90 个自动映射（83%），~15 个需确认，~13 个无对应

映射建立后写入 `concept_stats.planning_weight`，一次性迁入完成。

---

## §5 前端设计

### 5.1 节点视觉改进

当前节点只用审核状态着色（ai_draft=灰/reviewed=蓝/published=绿），信息密度低。

改进方案 — **双通道着色 + 尺寸编码**:

```
节点大小 ∝ importance_score (5-15px radius)
节点填充 = 着色模式决定:
  模式1 考频热力: 白(0)→浅蓝(1-50)→蓝(50-200)→深蓝(200-500)→紫(500+)
  模式2 掌握度:  灰(unseen)→红(weak)→黄(fragile)→绿(solid)
  模式3 审核状态: 灰(ai_draft)→蓝(reviewed)→绿(published)
节点边框 = 教学进度: 无(未计划)→蓝虚线(计划中)→绿实线(已教)
```

### 5.2 着色模式切换

图谱工具栏增加三个 radio button：`考频` | `掌握度` | `审核状态`

默认：教师进入时显示考频热力（最有信息量），选择学生后自动切换到掌握度。

### 5.3 图层切换

图谱工具栏增加复选框：
- [x] 硬前置关系（默认开）
- [ ] 软前置关系
- [ ] 桥接关系
- [ ] 对比关系
- [ ] 共现关系

### 5.4 详情面板增强

NodeDetailDrawer 新增标签页：

```
基本信息 | 课标 | 教材 | DA | 高考真题 | 学习单元
                                 ↑ 新增      ↑ 新增
```

**高考真题标签页**:
- 关联题数统计（总数 + 按年份/题型分布）
- 题目列表（题干截断 + 难度星级 + 年份 + 题型标签）
- 点击展开完整题目（含答案和解析）

**学习单元标签页**:
- StudyUnit 基本信息（ID、建议课时）
- 前置学习单元链
- 关联教材定位
- 推荐练习题家族
- DA 观察行为列表

### 5.5 教材章节导航

TreeNavPanel 增加导航模式切换：

```
按模块:    M1 → BC_M1_C1 → 概念列表
按教材章节: 必修1 → 第1章 → 第1节 → 概念列表
```

教材章节导航数据来源：`concept_stats.textbook_chapters` → 反向聚合为 book→chapter→section→concepts 树。

### 5.6 ModuleOverviewPanel 增强

模块卡片增加统计信息：

```
┌─────────────────────────┐
│ M1 分子与细胞            │
│                         │
│ 概念: 33    边: 89       │
│ 高考覆盖: 96%  平均考频: 186 │
│ ██████████░░  掌握度: 72% │  ← 班级掌握度条（教师选班后可见）
│                         │
│ 🔴 高频薄弱: ATP、细胞呼吸   │  ← 高考高频+班级薄弱 的交集
└─────────────────────────┘
```

---

## §6 Phase 实施优先级

| Phase | 内容 | 价值 | 依赖 | 预估规模 |
|-------|------|------|------|---------|
| **Phase 1** | 数据暴露 | 教师立刻看到有价值的图谱 | 无 | ~12 Task |
| **Phase 2** | 图谱增强 | 关联更丰富 | Phase 1 | ~6 Task |
| **Phase 3** | 教学规划 | 服务"规划教学"目标 | Phase 1 | ~8 Task |
| **Phase 4** | 学生画像+推荐 | 服务"画像+推送"目标 | Phase 1 + 数据管线 | ~8 Task |

**Phase 1 是基础**。它不需要新数据源，只需要计算+暴露已有数据，价值密度最高。

### Phase 1 Task 分解预览

| Task | 内容 | 类型 |
|------|------|------|
| T1 | concept_stats 模型 + 迁移 | 后端 |
| T2 | concept_stats 计算服务（考频/章节/重要度） | 后端 |
| T3 | MCU 规划权重映射 + 导入 | 后端+脚本 |
| T4 | sync_service 集成 concept_stats 计算 | 后端 |
| T5 | Graph API v3（合并 stats 到节点返回） | 后端 |
| T6 | 概念高考真题 API | 后端 |
| T7 | 统计概览 API | 后端 |
| T8 | 前端节点视觉升级（大小+热力着色） | 前端 |
| T9 | 前端着色模式切换工具栏 | 前端 |
| T10 | NodeDetailDrawer 高考真题标签页 | 前端 |
| T11 | NodeDetailDrawer 学习单元标签页 | 前端 |
| T12 | 教材章节导航模式 | 前端 |

---

## §7 技术决策

### 7.1 concept_stats 计算时机

**决策**: 启动时一次性计算 + 编辑操作后增量刷新。

**理由**: knowledge.db 数据相对静态（非实时变化），启动时全量计算耗时 <5s（108 L1 × 几次 SQL JOIN），无需定时任务。编辑图谱（add/remove/update 概念或边）后触发受影响概念的 stats 重算。

### 7.2 考频计算方法

**链路**: concept → DA (linked_concept_ids 反查) → Q-Matrix (attribute_id) → assessment_items (item_id)

**SQL 实现（在 knowledge.db 上执行）**:

```sql
SELECT c.id, COUNT(DISTINCT q.item_id) as exam_frequency
FROM concepts c
JOIN diagnostic_attributes da ON da.linked_concept_ids LIKE '%' || c.id || '%'
JOIN q_matrix q ON q.attribute_id = da.id
WHERE c.knowledge_level = 'L1'
GROUP BY c.id
```

注：`linked_concept_ids` 是 JSON 数组存为 TEXT，LIKE 匹配足够（156 DA 数据量小）。精确匹配可用 `json_each()` 但 SQLite 版本需确认。

### 7.3 importance_score 公式

```
importance_score = normalize_to_10(
    0.4 × exam_frequency_percentile +
    0.3 × error_prone_score +
    0.2 × transfer_value +
    0.1 × prerequisite_depth_factor
)
```

- `exam_frequency_percentile`: 考频在所有概念中的百分位（0-1）
- `error_prone_score`: 来自 MCU planning_weight.error_prone（无 MCU 映射时用 DA common_errors 数量替代）
- `transfer_value`: 来自 MCU planning_weight.transfer_value（无映射时用概念出度替代）
- `prerequisite_depth_factor`: 拓扑排序深度越深越基础越重要（反比）

### 7.4 教材章节映射计算

```
concept.evidence_ids_json → evidence concepts → source_block_id → content_blocks → sections
```

每个 L1 概念通过其 evidence（L0 知识点）回溯到教材节，聚合为 `[{book: "b1", chapter: "ch03", section: "s02", title: "..."}]`。

### 7.5 掌握度着色 vs 考频着色

两种着色模式互斥，通过工具栏切换。默认显示考频（教师最关心），选择学生后自动切换到掌握度。

**关键决策**: 不做双通道叠加（太复杂），用简单的模式切换。教师的核心场景是：
1. 备课时看考频（"什么重要"）
2. 看学生时看掌握度（"这个学生哪里弱"）

两个场景不同时发生，切换足够。

---

## §8 风险与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| MCU CP→concept 语义匹配准确率不足 | 权重数据迁入不全 | 无法自动匹配的 CP 手动确认，最差情况用 knowledge.db 自有数据替代 |
| 考频分布极端偏斜（最高 1313，中位 11） | 热力图颜色区分度差 | 使用对数尺度或百分位映射 |
| 前端节点数增加后布局拥挤 | 视觉混乱 | Phase 2 的图层切换限制同时显示的边数 |
| 教学计划功能使用率低 | 投入产出不匹配 | Phase 3 优先级低于 1/2，可根据反馈决定是否推进 |
| answer_logs 数据管线工程量大 | Phase 4 延期 | Phase 4 独立于 1/2/3，可以在生产部署后逐步接入 |

---

## §9 验收标准

### Phase 1 验收

- [ ] 教师打开知识图谱，节点大小反映重要度，颜色反映考频
- [ ] 点击任意节点，详情面板可看到关联的高考真题列表
- [ ] 点击任意节点，详情面板可看到学习单元信息
- [ ] 工具栏可切换着色模式（考频/掌握度/审核状态）
- [ ] 可通过"按教材章节"模式导航知识点
- [ ] ModuleOverviewPanel 显示考频分布和覆盖率统计
- [ ] concept_stats 在启动时自动计算完成（<10s）
- [ ] 所有已有测试通过 + 新增测试覆盖新功能

### Phase 2 验收

- [ ] 图层切换可控制显示 soft/bridge/contrast/共现边
- [ ] 边的粗细反映 strength × confidence
- [ ] 不同类型的边有不同的视觉样式（虚线/颜色/箭头）

### Phase 3 验收

- [ ] 教师可创建教学计划，将概念分配到教学周次
- [ ] 系统可生成建议教学序列
- [ ] 图谱上可看到教学进度（已教/计划中/未计划）

### Phase 4 验收

- [ ] 教师选择学生后，图谱按掌握度着色
- [ ] 系统可推荐学生下一步学习的概念和练习题
- [ ] 推荐基于前置依赖+掌握度+重要度

---

## §10 与现有系统的关系

| 现有模块 | 关系 | 变更 |
|---------|------|------|
| knowledge_tree/service.py | 核心修改 | get_graph() 扩展返回 stats |
| knowledge_tree/models.py | 新增模型 | ConceptStats, TeachingPlan, TeachingPlanItem |
| knowledge_tree/sync_service.py | 扩展 | 启动时触发 stats 计算 |
| knowledge_tree/detail_service.py | 扩展 | 新增高考题查询 |
| knowledge_tree/router.py | 新增端点 | exam-items, stats, teaching-plans |
| knowledge_tree/quality_service.py | 不变 | — |
| adaptive/bkt_engine.py | 不变（Phase 4 消费方）| — |
| adaptive/models.py | 不变 | — |
| frontend ConceptMapPanel.vue | 核心修改 | 节点视觉+着色模式 |
| frontend NodeDetailDrawer.vue | 扩展 | 新增标签页 |
| frontend TreeNavPanel.vue | 扩展 | 教材章节导航模式 |
| frontend useKnowledgeTree.js | 扩展 | 新数据源 |
| frontend knowledgeTree.js | 扩展 | 新 API 函数 |
