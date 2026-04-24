# 好分数 vs edu-cloud Phase 2 业务对比与填补设计

**Date**: 2026-04-24
**Author**: Claude Opus 4.7 (1M context) · brainstorming session
**Type**: T3 平台级 design（覆盖 S1-S4 四 Sprint）
**Status**: Draft v0.1 —— 等待用户 review
**Predecessor**: [Phase 1 Haofenshu Biz Replication Design (2026-04-12)](./2026-04-12-haofenshu-biz-replication-design.md)

---

## 0. TL;DR

本 design 定位为 **Phase 2 业务逻辑层**，在 Phase 1 UI 骨架之后推进。目标是用 `~/projects/haofenshu-clone/` 的业务逻辑填补 edu-cloud 在**教研教学闭环**上的缺口（题库 → 组卷 → 作业 → 错题 → 推送）。

采用**分层设计**（方案 C），分 4 Sprint 推进：

| Sprint | 层 | 工作量 | 核心 deliverable |
|---|---|---|---|
| **S1** | 数据层 | 1-2 周 | 题库/知识点/Grade schema 扩展 + 学情画像 VO |
| **S2** | 领域服务 | 4-6 周 | 题库搜索 + 组卷引擎 + 作业编辑器 + 考情分析 |
| **S3** | 闭环编排 | 3-4 周 | 错题推送联动 + 学情画像前端 + 精准教学控制台 |
| **S4** | 资源治理 | 3-4 周 | 备课资源库 + 试卷权限 + 教学计划 + 协同骨架 |

总工作量 11-16 周，通过并发 subagent 压缩到 **8-10 周**。执行模型：**8 会话（每 Sprint plan + execute 各一）× 每会话 3-4 subagent = 约 28-32 并发 agent 席次**。

---

## 1. 背景与动机

### 1.1 用户需求
2026-04-24 用户提出：用好分数的业务逻辑填补和优化 edu-cloud。

### 1.2 已有基础
Phase 1（2026-04-12 启动，Batch 2 完成于 2026-04-14 R3 PASS）产出前端 Nuxt 骨架 + 菜单系统 + 8 模块路由。Phase 1 设计明确 non-goals 包含"代码移植"——即 Phase 1 只做 UI 骨架，业务逻辑留给 Phase 2。

本 design 即 Phase 2 的总体设计。

### 1.3 素材资源
- `~/projects/haofenshu-clone/`（600 文件，139 MB）
  - 前端：Nuxt 3，45 页面 17,632 行（非 minified）
  - 后端：Express.js 9 模块 4,089 行 + SQLite 28 张表
  - 文档：`docs/business-logic.md` 2,044 行 + `docs/route-analysis.md` 919 行
  - 侦查产物：45 端点真实响应 + 47 页截图 + 509 KB 种子数据
  - 性质：从 haofenshu.com 原站逆向工程并自主开发的完整复刻，源代码完全可读

### 1.4 范围边界

**本 design 覆盖**（In-scope）：
- 业务逻辑层：模型、服务、编排、前端消费
- 4 Sprint 的整体架构 + 每 Sprint 的 deliverable 粒度
- 跨 Sprint 接口契约与 Gate
- 并发执行的会话 + subagent 派发模型

**本 design 不覆盖**（Out-of-scope）：
- UI 骨架（归 Phase 1 Batch 3，另轨推进）
- 每 Sprint 的具体 plan（由各自 writing-plans 会话产出）
- 每个函数的实现细节（由 executor 会话产出）

---

## 2. 调研依据

### 2.1 四轴对照概览

| 轴 | 覆盖模块 | Gap 数（🔴/🟡）| 核心发现 |
|---|---|---|---|
| **A 阅卷分析** | 好分数 exam+report → edu-cloud exam/analytics/profile/grading/marking | 0 / 0 | 完全对齐，反而 edu-cloud 超前 5 项（联考/Rubric/扫描/G6/Agent） |
| **B 学情研究** | 好分数 study+research → edu-cloud knowledge_tree/adaptive/bank/profile | 3 🔴 / 3 🟡 | 题库+组卷生态、知识点 L3、考情分析 |
| **C 教学资源** | 好分数 work+lesson → edu-cloud homework/bank/paper/studio | **6 🔴** / 4 🟡 | 最空白：作业编辑器、错题闭环、资源库、试卷权限、题库模型、教学计划 |
| **D 行政配置** | 好分数 baseinfo+academic → edu-cloud student/school/calendar/menu/conduct | 1 🔴 | 年级聚合；其他 edu-cloud 全部超前（conduct/multi-school/RBAC） |

详细对照表、Gap 清单、file:line 证据见：
- [附录 A：A 轴阅卷分析域调研报告](./2026-04-24-haofenshu-research-axis-a.md)
- [附录 B：B 轴学情研究域调研报告](./2026-04-24-haofenshu-research-axis-b.md)
- [附录 C：C 轴教学资源域调研报告](./2026-04-24-haofenshu-research-axis-c.md)
- [附录 D：D 轴行政配置域调研报告](./2026-04-24-haofenshu-research-axis-d.md)

### 2.2 核心洞察

**真正需要从好分数吸收的是 B+C 两轴的"教研教学闭环"**：

```
题库（B+C 重叠）→ 组卷（B）→ 作业布置（C）→ 学生做题
                                                          ↓
                    推送资源/作业（C）← 知识点聚合（C）← 错题本（C）
```

此闭环 edu-cloud 从头到尾都是骨架或空白：
- `paper` 模块：53 行空壳（PaperService 空方法）
- `bank` 模块：232 行骨架（只有错题查询 + 统计）
- `homework` 模块：588 行基础 CRUD（无编辑器、无推送）
- `studio` 模块：440 行骨架（文档生成 + 审批流，无前端）

### 2.3 edu-cloud 超前清单（禁止倒退）

| 超前能力 | 覆盖度 | 对应好分数 |
|---|---|---|
| Conduct 德育模块 | 2416 行完整 | 无 |
| 联考 + 多校管理（district_admin） | 完整 | 仅 systemAdmin/schoolAdmin 两层 |
| Rubric AI 自动生成 | 完整 | 手动配置 |
| 扫描自动化 + 答题卡 AI 校准 | 完整 | 外部扫描软件 |
| 知识图谱 G6 可视化 | KnowledgeTreePage.vue 8675 行 + AntV G6 | 纯 el-tree |
| BKT 自适应学习 | bkt_engine + 7 表完整生态 | 简单百分比 |
| Agent 工具系统 | 62 工具 × 23 模块 | 无 AI 对话 |
| RBAC 34 权限 + DataScope | 8 角色 × 34 权限 × Scope 治理 | 3 角色，scope 内嵌 |
| 学生 Excel 导入（完整） | import_students 400+ 行 | 仅导出无导入 |

**任何涉及上述模块的修改都必须评估是否会削弱现有能力**（见 §12 ORC-002）。

---

## 3. 架构方案：分层设计（L1-L4）

### 3.1 方案评估

brainstorming 中评估了 3 个方案：

| 方案 | 组织方式 | 优 | 劣 |
|---|---|---|---|
| A 分轴独立 | 按 B/C/D 三轴分别推进 | 分工清晰 | 题库/知识点跨轴重复 + 跨轴接口对齐成本 |
| B 闭环优先 | 按教研闭环（题库→组卷→作业→错题→推送）串行 | 端到端对齐 | 强依赖阻塞 + 基础数据层散落 |
| **C 分层设计**（**选定**） | L1 数据 / L2 服务 / L3 编排 / L4 治理 | 层次清晰、并发友好、基础层先行 | 前置要求高（S1 必须一次到位） |

### 3.2 方案 C 选定理由

1. **edu-cloud 缺失集中在数据模型层**——bank_question 字段稀疏、concept_graph 只有 2 层、无 teaching_plans 表——先整 L1 能消除 60% 下游不确定性
2. **好分数业务逻辑本身是分层的**：`business-logic.md` + `schema.sql` 的组织确实是 entity → service → orchestration → UI policy
3. **并发执行友好**：L2-L4 在 L1 契约冻结后可受控并发（会话层 + subagent 层两级并发）
4. **决策证据可集中锚定**：L1 Evidence Block 一次把跨层决策的证据固定

### 3.3 分层结构图

```
┌────────────────────────────────────────────────────┐
│  L4 资源治理 (S4, 3-4 周)                           │
│  4.1 资源库  4.2 试卷权限  4.3 教学计划  4.4 协同  │
├────────────────────────────────────────────────────┤
│  L3 闭环编排 (S3, 3-4 周)                           │
│  3.1 错题→推送  3.2 学情画像前端  3.3 精准教学     │
├────────────────────────────────────────────────────┤
│  L2 领域服务 (S2, 4-6 周)                           │
│  2.1 题库搜索 2.2 组卷 2.3 作业编辑 2.4 考情分析   │
├────────────────────────────────────────────────────┤
│  L1 数据层 (S1, 1-2 周)                             │
│  1.1 题库模型 1.2 知识点 L3 1.3 Grade 表            │
│  1.4 教学计划骨架 1.5 试卷权限枚举 1.6 学情 VO      │
└────────────────────────────────────────────────────┘
           ↑                      ↑
      好分数参照              edu-cloud 现状
   (附录 A-D file:line)      (现有 Alembic + 模块)
```

---

## 4. L1 数据层（S1）

### 4.1 Deliverables

| ID | Deliverable | 好分数对照（来源） | 工作量 |
|---|---|---|---|
| 1.1 | `bank_question` 表扩展 | 附录 C Gap#5 + `haofenshu-clone/server/config/schema.sql:232-245` | S |
| 1.2 | `concept_graph_nodes` 加 `depth_level` 枚举（subject/unit/core/point） | 附录 B Gap#2 + `haofenshu-clone/server/config/schema.sql:215-225` | M |
| 1.3 | 新建 `grades` 独立表 + `Class.grade_id` 外键 | 附录 D Gap#1 + `haofenshu-clone/server/routes/baseinfo.js` | S |
| 1.4 | `teaching_plans` 表骨架（仅 schema） | 附录 C Gap#6 + `haofenshu-clone/server/config/schema.sql:284-302` | S |
| 1.5 | `paper_access_level` 枚举常量 | 附录 C Gap#4（试卷权限分层） | XS |
| 1.6 | `StudentProfileView` Pydantic VO（聚合既有 snapshot + mastery + errors） | 附录 B Gap#1（学情画像） | S |

**1.1 字段变更**：

```python
# Alembic migration: extend_bank_question
# +字段:
# - source: Enum('textbook', 'exam', 'custom', 'imported')
# - explanation: Text (题目解析)
# - tags: JSON (array of str)
# - knowledge_point_ids: JSON (array of int, FK to concept_graph_nodes)
# - grade_id: Integer (FK to grades, new)
# - difficulty_level: Enum('easy', 'medium', 'hard')  # 独立于 difficulty 系数
# - bloom_level: Enum('remember', 'understand', 'apply', 'analyze', 'evaluate', 'create') nullable
```

**1.2 L3 层级映射**：

| 好分数层级 | edu-cloud `concept_graph_nodes.depth_level` | 现有数据迁移 |
|---|---|---|
| 学科 | `subject` | 顶层新增 |
| 大单元 | `unit` | 从 `big_concept` 映射 |
| 核心知识 | `core` | 从 `concept` 升级 |
| 具体知识点 | `point` | 新增叶子节点，初始用占位 |

### 4.2 Alembic 迁移策略

- **一次性 migration**（不允许分拆），包含 1.1/1.2/1.3/1.4/1.5 所有 schema 变更
- 必须支持 `alembic upgrade` 和 `downgrade` 双向
- **生产库（mcu.asia）迁移前**必须先在本地 seed 库测试
- 迁移前跑 `sqlite3 ".backup"`（CLAUDE.md L016，禁 `cp`）

### 4.3 Evidence Block

```
decision: S1 一次性冻结所有 L1 schema 变更
evidence_refs:
  - 附录 B Gap#2 — 知识点 L3 未定 → 组卷/诊断精度受影响
  - 附录 C Gap#5 — bank_question 字段稀疏 → 下游作业/错题本依赖
  - 附录 D Gap#1 — Grade 缺独立表 → 年级聚合受影响
Q1: evidence_source: agent-surveyed-code, evidence_state: verified
Q2_excluded:
  - "逐 Sprint 扩字段": 反证路径: 如果分散扩展，每个 Sprint 都要调整 Alembic，并发开发会冲突；edu-cloud 现有 alembic/versions/ 数量 20+ 印证渐进式代价
impact_scope: system
unknowns:
  - 生产库 mcu.asia 当前数据量 / 索引对 migration 性能影响
followup_spike: S1 Day 1 查 mcu.asia concept_graph_nodes + bank_question 现有行数
```

---

## 5. L2 领域服务层（S2）

### 5.1 Deliverables

| ID | Deliverable | 依赖 L1 | 工作量 |
|---|---|---|---|
| 2.1 | `bank.search_service`：source/difficulty/kp/tags/grade 过滤 + SQLite FTS5 全文 | 1.1 | M |
| 2.2 | `paper.composer_service`：4 策略（Quick/KnowledgePoint/Blueprint/Chapter） | 1.1 + 1.2 + 1.4 | L |
| 2.3 | `homework.editor_service`：扩展 content JSON schema（题目引用/富文本/AI 推荐元） | 1.1 | M |
| 2.4 | `analytics.exam_trend_service`：多次考试聚合 + 出题频率 + 雷达数据 | 1.2 | M |

**2.2 组卷策略接口**：

```python
class ComposeStrategy(Protocol):
    def compose(self, constraints: ComposeConstraints) -> List[Question]: ...

class QuickCompose(ComposeStrategy): ...         # 按数量随机
class KnowledgePointCompose(ComposeStrategy): ...# 按知识点覆盖
class BlueprintCompose(ComposeStrategy): ...     # 按题型占比 + 难度分布
class ChapterCompose(ComposeStrategy): ...       # 按 teaching_plans 章节
```

### 5.2 性能基线

| 服务 | 基线 | 测量场景 |
|---|---|---|
| 2.1 题库搜索 | P99 < 500ms | 10k 题目数据集 |
| 2.2 组卷（50 题） | P99 < 2s | KnowledgePointCompose @ 100 kp |
| 2.3 作业编辑保存 | P99 < 300ms | 20 题引用 + 2KB rich text |
| 2.4 考情分析 | P99 < 1s | 近 3 学期 100 次考试 |

**Gate G2 通过条件**：任一服务性能未达基线 → S2 不完整，S3 相关功能不启动。

### 5.3 Evidence Block

```
decision: S2 采用 SQLite FTS5 而非 Elasticsearch 做全文检索
evidence_refs:
  - 附录 C Gap#5 — 好分数题库最大约 50k 题，SQLite FTS5 足够
  - `edu-cloud/alembic/versions/` 零 ES 依赖
  - 生产环境 mcu.asia 单机 VM，无 ES 部署
Q1: evidence_source: code-grep + deployment-topology, evidence_state: verified
Q2_excluded:
  - Elasticsearch: 反证路径: 部署/运维成本高，单机 VM 不合适；edu-cloud 历史选型已排除 ES
impact_scope: module (bank)
unknowns: none
```

---

## 6. L3 闭环编排层（S3）

### 6.1 Deliverables

| ID | Deliverable | 依赖 | 工作量 |
|---|---|---|---|
| 3.1 | `bank.error_orchestrator`：错题本→adaptive 诊断→homework 布置跟踪作业 | 2.3 + 现有 adaptive | M |
| 3.2 | `StudentProfilePage.vue`：学情画像综合页（4 tab：趋势/知识掌握/错题/对标） | 1.6 VO | S |
| 3.3 | `lesson.teaching_desk_service`：精准教学控制台 | 2.4 + 3.1 | M |

### 6.2 UI 验收策略（L015 感知型任务纪律）

3.2 学情画像页是**感知型任务**，Claude 绝不自行声称"对齐/已完成"：

1. 完成每一版本后输出：
   - Playwright 截图路径
   - 好分数对应页面截图路径（`haofenshu-clone/data/screenshots-v2/`）
   - 差异说明（至少 3 个维度：布局/内容/交互）
   - 结论："待用户确认"
2. **禁止输出**任何"✓/PASS/对齐"的自我裁定
3. 用户明确 confirm 后才能标 G3 通过

### 6.3 Evidence Block

```
decision: S3 学情画像页复用 L1 VO（1.6），零新表
evidence_refs:
  - 附录 B Gap#1 — 现有 StudentExamSnapshot/StudentKnowledgeMastery/StudentErrorPattern 齐全
  - `edu-cloud/src/edu_cloud/modules/profile/service.py:26-41` — 既有聚合逻辑
Q1: evidence_source: code-grep, evidence_state: verified
Q2_excluded:
  - "新增 StudentProfile 表": 反证路径: 现有表覆盖字段完整，新增等于重复；Grep "StudentProfile$" 零结果
impact_scope: module (profile)
unknowns: none
```

---

## 7. L4 资源治理层（S4）

### 7.1 Deliverables

| ID | Deliverable | 依赖 | 工作量 |
|---|---|---|---|
| 4.1 | `studio.resource_library`：5 分类（课件/讲评/组卷/教案/视频）+ 前端库页 | 现有 studio + 2.2 | M |
| 4.2 | `paper.access_policy`：3 层分享工作流（teacher/school/district）+ 审批 | 1.5 | M |
| 4.3 | `calendar.teaching_plan_service`：学期→周次→知识点→资源绑定 + TeachingPlanEditor.vue | 1.4 + 4.1 | M |
| 4.4 | `studio.collab_service`：多用户编辑 simple lock + ApprovalWorkbench.vue | 4.1 | M |

### 7.2 Evidence Block

```
decision: S4 协同编辑采用 simple lock 而非 CRDT
evidence_refs:
  - 附录 C 有价值优化#2 — 协同编辑需求规模小（学校级，教师数个位数）
  - edu-cloud 无 WebSocket 基础设施
Q1: evidence_source: code-grep, evidence_state: verified
Q2_excluded:
  - CRDT: 反证路径: 引入 yjs/automerge 成本超过教师数 × 编辑频率 × 冲突率的价值
  - OT: 反证路径: 同上
impact_scope: module (studio)
unknowns: simple lock 并发编辑 UX 是否可接受（S4 spike）
followup_spike: S4 Day 1 mock 并发编辑场景让用户试用 simple lock
```

---

## 8. 跨层接口契约

### 8.1 原则

1. **L1 → L2/L3/L4**：严格 Pydantic schema + SQLAlchemy model。**上层不得扩展 L1 字段**，发现需扩必须退回 S1 补丁（Gate G1 后重开）
2. **L2 → L3**：走 service.py，**L3 不直接操作 L2 的数据库**（enforce 通过代码审查）
3. **L3 → L4**：近乎无依赖（4.3 使用 4.1 的 Document，4.1 使用 2.2 产物，但 L3 和 L4 直接耦合仅限于 3.3 使用 4.1 资源）
4. **任何层 → 好分数对照**：每个新增/修改的字段或端点在代码注释 / docstring 中注明 `refs: haofenshu-clone/{path}:{line}` 或 `refs: 附录{X} §{Gap#}`

### 8.2 跨层共享实体清单

| 实体 | L1 定义位置 | 被谁消费 |
|---|---|---|
| `BankQuestion`（扩展后） | 1.1 | 2.1/2.2/2.3/3.1 |
| `ConceptGraphNode`（加 depth_level） | 1.2 | 2.2/2.4/3.1 |
| `Grade`（新） | 1.3 | 2.2/2.4/4.3 所有年级聚合 |
| `TeachingPlan`（骨架） | 1.4 | 2.2 ChapterCompose / 4.3 |
| `PaperAccessLevel`（枚举） | 1.5 | 4.2 |
| `StudentProfileView`（VO） | 1.6 | 3.2（仅前端消费） |

### 8.3 禁止的跨层操作

1. L2 服务不得注入 L3 编排逻辑（例如 2.1 题库搜索不得"自动推送"）
2. L3 编排不得直接改 L1 schema（需经 S1 补丁）
3. L4 治理组件不得重复 L2 服务逻辑（复用而非再造）

---

## 9. Sprint 划分与 Gate 设计

| Sprint | 工作量 | Gate | 通过条件 |
|---|---|---|---|
| **S1** | 1-2 周 | **G1 数据模型冻结** | Alembic up/down 在空 db + mcu.asia 生产库 dump 都能跑；所有 L1 deliverables 合并 commit |
| **S2** | 4-6 周 | **G2 性能基线** | 2.1/2.2/2.3/2.4 任一未达 §5.2 基线 → Gate 不通过 |
| **S3** | 3-4 周 | **G3 用户 UI 确认** | 3.1/3.3 端到端测试 + 3.2 学情画像页用户明确 confirm（感知型任务） |
| **S4** | 3-4 周 | **G4 integration review** | codex-review integration 全 PASS + S4 内部集成测试通过 |

Gate 不通过 → 下游 Sprint **不启动 executor session**（writing-plans 可以先行准备）。

---

## 10. 并发执行策略

### 10.1 会话级流转（8 会话）

```
[会话 A] 当前 (brainstorming + writing-plans) → S1 plan commit → stop
   ↓ codex-review plan (gates.json 硬拦截)
[会话 B] executing S1 (用户新开)
   ↓ G1 通过 + handoff.md
[会话 C] writing S2 plan (新)
   ↓ codex-review
[会话 D] executing S2 (新)
   ↓ G2 通过
[会话 E] writing S3 plan (新)
[会话 F] executing S3 (新) → G3 UI 确认
[会话 G] writing S4 plan (新)
[会话 H] executing S4 (新) → G4 integration review
```

**每 Sprint 至少 2 会话**（plan + execute），CLAUDE.md `session_guard` 硬拦同会话 writing-plans + executing-plans。

### 10.2 Sprint 内部 subagent 分工

| Sprint | 子 agent | 分工 | 依赖关系 |
|---|---|---|---|
| **S1** | 3 | ① 1.1+1.2 schema ② 1.3+1.4+1.5 schema ③ 1.6 VO | 完全并发，最后合并 Alembic 一次 commit |
| **S2** | 4 | ① 2.1 ② 2.2 ③ 2.3 ④ 2.4 | 完全并发（L1 已冻结） |
| **S3** | 3 | ① 3.2（独立） ② 3.1（依赖 adaptive） ③ 3.3（依赖 3.1+2.4） | 3.2 并 3.1→3.3 |
| **S4** | 4 | ① 4.1 ② 4.2 ③ 4.3（依赖 4.1） ④ 4.4（依赖 4.1） | 4.1+4.2 并发 → 4.3+4.4 并发 |

**总计：8 会话 × 3-4 subagent = 约 28-32 并发 agent 席次**，分布在 8-10 周执行窗口。

### 10.3 Handoff 纪律

每 Sprint 结束写 `docs/plans/2026-04-XX-haofenshu-s{N}-handoff.md`：

- CLAUDE.md `handoff_format_guard` 8-Check
- **≤15 行硬限**（防 Stop hook 爆量）
- 同 topic handoff ≤1 次
- 触发点：executor 会话 Stop 前

### 10.4 Review 嵌入

| 时机 | Review 类型 | 拦截等级 |
|---|---|---|
| plan commit | `codex-review plan` | gates.json 硬拦截，不过不能启动 executor |
| 每 batch code（约 2-4 files） | `codex-review code` R1 | R1 FAIL 必须修复才能进下 batch，R3+ 禁止 |
| S4 完成 | `codex-review integration` | 集成 review |

**GPT finding 三分**（L017 源头治理）：
- `defect_fix`：缺陷，可批量处置
- `test_gap`：测试缺口
- `design_concern`：设计层关注（GPT 禁提修复方案，需设计者决策）

---

## 11. 验收标准

### 11.1 通用 DoD（所有 Sprint）

1. pytest / vitest 全绿 + ruff / mypy 无新增 violation
2. 所有新 HTTP 端点有 `require_permission` 装饰（RBAC 34 权限）
3. service 层单测 + router 层集成测试
4. 新模块 README + OpenAPI schema 注解
5. 负面断言必须附 Grep 零结果
6. 新增/修改字段或端点必须注明好分数对照（`refs: 附录{X} §{Gap#}`）

### 11.2 Sprint 专属 DoD

| Sprint | 特殊验收 |
|---|---|
| **S1** | Alembic up/down 可逆（空 db + mcu.asia 生产库 dump 都能跑）；VO 聚合在现有数据上跑通 |
| **S2** | 组卷引擎至少 3 策略跑通（Quick/KnowledgePoint/Blueprint）；§5.2 性能基线全达标 |
| **S3** | 错题→推送端到端测试；学情画像页 UI 验收由用户裁定；Playwright 截图留证 |
| **S4** | 5 分类资源库完整 CRUD；3 层试卷权限分享工作流；协同 simple lock 在并发编辑下防冲突 |

### 11.3 用户验收点（Claude 不越权）

按 CLAUDE.md L013/L015 纪律，以下**只由用户裁定**：

1. S1 数据模型语义（用户看 Alembic diff）
2. S2 组卷结果合理性（用户看 sample 试卷）
3. **S3 学情画像页视觉还原度**（感知型，严禁 Claude 声称"对齐"）
4. S4 资源库前端交互

---

## 12. 不可违反的设计决策（semantic_regression 候选）

后续每个 Sprint 的 plan 必须从本节提炼 `semantic_regression` 段（CLAUDE.md L017 源头治理）：

### ORC-001：L1 数据模型冻结后上层 Sprint 不得扩展 L1 字段
- **Why**：避免下游并发开发的 schema 漂移，防止 S2/S3/S4 各自改 L1 引起合并冲突和数据不一致
- **How to apply**：codex-review plan 阶段检测 Sprint 交叉 schema 变更；发现扩展需求必须退回 S1 重开一个 patch session

### ORC-002：edu-cloud 超前能力清单禁止倒退
- **Why**：防止 GPT 审查建议覆盖全局设计（L017 局部最优 vs 全局最优）
- **How to apply**：修改 §2.3 清单中任何模块的 PR，必须额外 human review；GPT finding 即使是 defect_fix 也要 design_concern 级别人工决策

### ORC-003：感知型任务验收权归用户
- **Why**：CLAUDE.md L015 事故纪律。Claude 无法量化视觉还原度
- **How to apply**：S3 学情画像页必须输出 Playwright 截图 + 好分数对照截图 + 3 维度差异说明；严禁输出"✓/对齐/已完成"

### ORC-004：好分数对照可追溯
- **Why**：决策证据纪律（CLAUDE.md rules/decision-evidence.md）+ 便于后续调整
- **How to apply**：每个 deliverable 必须附 `refs: 附录{X} §{Gap#}` 或 `refs: haofenshu-clone/{path}:{line}`；codex-review 检查 refs 是否存在

### ORC-005：Sprint Gate 串行不可并跳
- **Why**：防止下游 executor 基于未定型的上游假设展开工作
- **How to apply**：CLAUDE.md session_guard + codex-review gates.json 硬拦截；writing-plans 可以超前（不落地），executing 必须按顺序

---

## 13. Evidence Blocks（关键决策证据锚定）

### 13.1 聚焦 B+C 轴，A/D 轴最小介入

```
decision: 本 design deliverables 集中在 B+C 两轴；A 轴无 deliverable；D 轴仅 1 项（Grade 表）
evidence_refs:
  - 附录 A — 20 项能力对照，0 Gap，"edu-cloud 覆盖率 100%"
  - 附录 D — conduct/multi-school/RBAC edu-cloud 全部超前
  - 附录 C — 6 项 🔴 高价值 Gap
Q1: evidence_source: agent-surveyed-code, evidence_state: verified
Q2_excluded:
  - "全轴均衡投入": 反证路径: 如果 A 轴有 Gap，调研应发现 ≥1 项，但实际 0 项
impact_scope: system
unknowns: none
```

### 13.2 分层设计（L1-L4）而非分轴

```
decision: 采用 L1-L4 分层，而非按 B/C/D 轴切 Sprint
evidence_refs:
  - 附录 C 6 Gap 中 5 个跨 B+C（题库/知识点/错题/作业推送）
  - 附录 B Gap#1 与 附录 C Gap#5 都涉及题库模型
  - haofenshu-clone/docs/business-logic.md 结构：entity → service → orchestration → UI
Q1: evidence_source: doc-read + agent-surveyed-code, evidence_state: verified
Q2_excluded:
  - "分轴独立": 反证路径: C 轴 6 Gap 中若切到 B 轴会重复题库设计；附录 B Gap#1 + 附录 C Gap#5 有重叠
impact_scope: cross-module
unknowns: 跨层接口精确 schema 细节（S1 落地才能确定）
followup_spike: S1 第一周接口契约 spike
```

### 13.3 S1 schema 冻结 Gate 前置

```
decision: S1 完成 → Gate G1 → 数据模型冻结声明 → 才能启动 S2/S3/S4 executor
evidence_refs:
  - 附录 B Gap#2 — 知识点 L3 未定 → 组卷精度受影响
  - 附录 C Gap#5 — bank_question 字段稀疏 → 下游作业/错题本依赖
  - edu-cloud 现有 alembic/versions/ migration 数量（grep count）印证渐进式 schema 变更历史代价
Q1: evidence_source: agent-surveyed-code + file-count, evidence_state: verified
Q2_excluded:
  - "分散扩展 schema": 反证路径: 每 Sprint 各改 L1 会导致 Alembic 合并冲突；并发开发下 S2 的 2.2 组卷可能依赖 S3 还没定的 concept.depth_level
impact_scope: system
unknowns: mcu.asia 生产库当前数据量对 migration 性能影响
followup_spike: S1 Day 1 查生产库行数 + 索引
```

### 13.4 SQLite FTS5 vs Elasticsearch

```
decision: 2.1 题库搜索用 SQLite FTS5
evidence_refs:
  - edu-cloud/alembic/versions/ 零 ES 依赖
  - 生产环境 mcu.asia 单机 VM
  - 附录 C Gap#5 — 题库规模 ≤50k 题（好分数参照）
Q1: evidence_source: code-grep + deployment-topology, evidence_state: verified
Q2_excluded:
  - Elasticsearch: 反证路径: 部署/运维成本 vs 题库规模不匹配；单机 VM 无法额外运行 ES JVM
impact_scope: module (bank)
unknowns: none
```

---

## 14. 附录

- [附录 A：A 轴阅卷分析域调研报告](./2026-04-24-haofenshu-research-axis-a.md) — 20 项能力对照，0 Gap
- [附录 B：B 轴学情研究域调研报告](./2026-04-24-haofenshu-research-axis-b.md) — 3 🔴 + 2 🟡 Gap
- [附录 C：C 轴教学资源域调研报告](./2026-04-24-haofenshu-research-axis-c.md) — 6 🔴 + 4 🟡 Gap（最空白）
- [附录 D：D 轴行政配置域调研报告](./2026-04-24-haofenshu-research-axis-d.md) — 1 🟡 Gap

---

## 变更日志

- **2026-04-24 v0.1** 初稿（brainstorming session by Claude Opus 4.7 1M context；基于 4 个并发 Explore agent 的对照调研）—— 等待用户 review
