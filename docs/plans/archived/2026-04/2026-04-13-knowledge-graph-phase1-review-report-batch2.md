[edu-cloud] GPT Reviewer | 2026-04-13 19:58:38

## 审查报告: Batch 2 (T7-T8) — Round 1

**结论: FAIL**

- 代码范围: commit `ff59672`（feat: Batch 2 T7/T8 — Graph API v3 + exam-items + stats/overview）
- 交接单: `docs/plans/2026-04-13-knowledge-graph-phase1-review-handoff-batch2.md`
- 原始输出: `docs/plans/.codex-raw-code_review_batch2-20260413T195830.log`
- 原始 SHA256: `243caa0be9b6f57f924b148a5eba0c249fb700b5bffaaf441a0172303ac42524`

### 第一段：测试充分性（Test Adequacy）

GPT 实际跑了 `test_graph_v3.py` / `test_exam_items_service.py` / Contract Pack 关联的存量测试，全部通过——但问题在"现有测试会在错误实现下仍绿"。

- **T7 Graph API v3**：`test_graph_v2_fields_preserved` + `test_curriculum_layer_present` 真正覆盖 INV-001（v2 字段保留 + curriculum 层新增），通过删除 v2 字段或返回空 curriculum 都会失败 → 充分。
- **T8 exam-items**：`test_exam_items_service.py` 的 9 项断言均为占位级（`total > 0` / `len(items) >= 1` / 字段存在 / 模块名集合），未锁定 DA→Q-Matrix→assessment_items 映射的链路正确性、分页切片语义、聚合数值精度。Mutant 测试（替换为硬编码占位）能绿通——见 F001/F002。
- **Contract Pack 一致性**：INV-001/INV-003 verification 映射成立；INV-002/INV-004/INV-005 映射不准——见 P001。CE-002 的"禁 4xx 视为通过" mitigation 已部分落实。

### 第二段：行为正确性（Behavioral Correctness）

**变更理解（GPT 独立复述）：**

本 Batch 实现 Knowledge Tree Phase 1 的 T7/T8 两个 Task：
- **T7 Graph API v3**：在现有 `GET /api/v1/knowledge-tree/graph` 响应中追加 `curriculum_layer`（按 `module` 字段聚合的 L1 ID 列表，依赖 PG 的 `concept_graph_nodes`）。v2 字段全保留。
- **T8 exam-items + stats/overview**：新增两个端点。`GET /graph/{node_id}/exam-items` 经 DA→Q-Matrix→assessment_items 链路返回某 L1 概念关联的题目（带分页）。`GET /stats/overview` 返回 module 维度聚合（avg_freq / exam_coverage / freq distribution / total_edges）。

**对抗性审查：**

- **入口验证**：T7 通过 router → service 链路有 `test_graph_v3` 覆盖；T8 两端点的测试只断言"返回非空 + 字段存在"，未锁定语义。
- **Mutant 测试反证**：GPT 复盘 `test_exam_items_service.py:31/68` 与 `:111/173`，确认占位实现（exam-items 返回任意非空 + overview 返回硬编码 M1/M2 + high/mid/zero）能绿通，**直接证伪测试有效性** → F001/F002 HIGH。
- **分页边界稳定性**：`get_exam_items()` 先做未排序 `DISTINCT item_id` Python 切片，再 `WHERE id IN (...)` 第二次未排序查询 → 翻页可能重复/漏题/抖动 → F003 MED。
- **Contract Pack 漂移**：plan 要求 T8 修改 `schemas.py` 提供新响应契约，实现仅新增 dict 返回，未引入 `response_model` → P002。

### 第三段：未测试风险（Non-tested Risks）

- exam-items 跨 batch 翻页一致性未测
- overview 聚合数值（avg_freq/exam_coverage/total_edges）未在受控数据集上精确断言
- response_model 缺失导致 OpenAPI schema 漂移风险
- Contract Pack INV-002/INV-004/INV-005 的"verification 映射不准"会让 Gate 2 误判

### 发现清单

<!-- anchor: finding-list -->

#### F001 — exam-items 测试无法证伪占位实现

- **Severity:** HIGH
- **Category:** test-gap
- **Type:** defect_fix
- **Status:** verified
- **Before-behavior:** `GET /graph/{node_id}/exam-items` 的测试在实现退化为"已知概念返回任意非空题目、未知概念返回空列表"时仍可通过，DA→Q-Matrix→assessment_items 的核心链路没有被真正锁定。
- **After-behavior:** 测试应能证明返回的题目确实来自目标概念关联的 DA 链路，并且分页边界基于该链路结果而不是任意占位数据。
- **Evidence:** `tests/test_knowledge_tree/test_exam_items_service.py:31`, `:68`; `docs/plans/2026-04-13-knowledge-graph-phase1-plan.md:1940`
- **Impact:** 错误的题目关联、跨概念串题、分页错链可能在 CI 绿灯下进入前端。
- **Repair hypothesis:** 方向是把 S7 提升为"入口级且可反证"的契约测试，直接锁定概念→题目映射正确性 + 分页切片语义。避免 `total > 0` + 字段存在等占位断言。requires independent fix design + Semantic Regression Gate。

#### F002 — stats/overview 测试无法证伪硬编码聚合

- **Severity:** HIGH
- **Category:** test-gap
- **Type:** defect_fix
- **Status:** verified
- **Before-behavior:** `/stats/overview` 测试只验证 key 存在 + `>= 1` + `> 0` + 模块名集合；即使聚合逻辑被替换成硬编码占位值（返回 `M1/M2` + `high/mid/zero` 即可），测试仍通过。
- **After-behavior:** 测试应在隔离数据集上精确断言 `avg_freq`、`exam_coverage`、`exam_freq_distribution`、`total_edges`，确保覆盖率分母、分桶阈值、模块过滤都能在错误实现下失败。
- **Evidence:** `tests/test_knowledge_tree/test_exam_items_service.py:111`, `:173`; `docs/plans/2026-04-13-knowledge-graph-phase1-plan.md:1947`
- **Impact:** 统计概览最关键的聚合回归不会被发现，前端模块卡片和分布图可能长期消费错误指标。
- **Repair hypothesis:** 方向是用完全受控的图节点/边/stats 种子把 S8 变成精确聚合测试。避免使用受全局 fixture 污染的"至少包含"断言。requires independent fix design + Semantic Regression Gate。

#### F003 — get_exam_items() 分页非确定性

- **Severity:** MED
- **Category:** code-bug
- **Type:** defect_fix
- **Status:** verified
- **Before-behavior:** `get_exam_items()` 先对未排序的 `DISTINCT item_id` 结果做 Python 切片，再对 `assessment_items WHERE id IN (...)` 做第二次未排序查询，分页顺序和页边界都不稳定。
- **After-behavior:** 分页应基于确定性的排序键，并在明细查询中保持同一顺序。
- **Evidence:** `src/edu_cloud/modules/knowledge_tree/exam_items_service.py:62`, `:83`
- **Impact:** 相同请求可能出现翻页重复/漏题/顺序抖动，前端分页体验不可预测。
- **Repair hypothesis:** 先定义题目列表的稳定排序语义（如按 `item_id ASC` 或 `created_at DESC, id ASC`），让取 ID 和取详情共用该顺序；避免依赖 SQLite 默认顺序或 `IN (...)` 子句的隐含顺序保留。requires independent fix design + Semantic Regression Gate。

#### P001 — Contract Pack invariant verification 映射不准

- **Severity:** MED
- **Category:** process（不阻塞 PASS/FAIL）
- **Type:** defect_fix
- **Status:** verified
- **Before-behavior:** Contract Pack 的多条 invariant verification 映射与当前测试事实不一致（INV-002 / INV-004 / INV-005）。
- **After-behavior:** verification 应精确指向真正覆盖该 invariant 的测试，且覆盖范围与 invariant 文案一致。
- **Evidence:** `docs/plans/2026-04-13-knowledge-graph-phase1-plan.md:3966/3976/3981`; `tests/test_knowledge_tree/test_stats_service.py:34`, `:162`; `frontend/src/__tests__/knowledge-tree/KnowledgeTreePage.test.js:1`
- **Impact:** Gate 2 会把"存在测试"误判成"已验证不变量"，降低 Contract Pack 的约束力。
- **Repair hypothesis:** Planner 更新 verification 映射。INV-002 需要"L1 集合相等"级别验证；INV-004 应指向真实组件契约/集成测试；INV-005 至少要把单调性测试纳入。

#### P002 — Task 8 schemas.py 契约缺失

- **Severity:** MED
- **Category:** process（不阻塞 PASS/FAIL）
- **Type:** defect_fix
- **Status:** verified
- **Before-behavior:** Task 8 计划要求修改 `schemas.py` 提供新响应契约，但实现直接新增两个 public API，未引入对应 response schema / `response_model`。
- **After-behavior:** public API 的契约层应与 plan/Contract Pack 同步，避免接口文档/验证/实现三者漂移。
- **Evidence:** `docs/plans/2026-04-13-knowledge-graph-phase1-plan.md:1932`; `src/edu_cloud/modules/knowledge_tree/router.py:91`, `:115`; `src/edu_cloud/modules/knowledge_tree/schemas.py:6`
- **Impact:** API 返回形状缺少框架边界校验，前端接入时易发生静默漂移。
- **Repair hypothesis:** Planner 更新 plan/Contract Pack，把 ExamItemsResponse / StatsOverviewResponse 显式化并接入 router 的 `response_model`。

### 行为变更审批记录

本批次 5 个 finding 全部为 `defect_fix`，无 `behavior_change`。红旗模式扫描通过：F001/F002 是测试加固；F003 是非确定性 → 确定性的 bug 修复（不是引入新行为）；P001/P002 是 plan 文档同步。无需用户单独批准。

### PASS/FAIL 判定

按 `~/.claude/rules-t3/review-templates.md <!-- anchor: pass-fail -->`：
- code-bug 或 test-gap 的 HIGH/MED 未修复 → FAIL
- F001 HIGH test-gap + F002 HIGH test-gap + F003 MED code-bug → **FAIL**
- P001/P002 process 不影响 PASS/FAIL 判定，由 Planner 在 plan/Contract Pack 中处置

### 处置建议

1. **F001/F002 加固测试**：替换占位断言为精确反证测试（独立 fixture + 精确数值断言）→ Round 2 重审
2. **F003 修复分页**：确定 `get_exam_items()` 的稳定排序键，让 IN 查询保持同序
3. **P001/P002 由 Planner 处置**：更新 Contract Pack INV-002/004/005 verification + 补 ExamItemsResponse / StatsOverviewResponse schema（可在 Round 2 一并修，也可放入下一 Task）
